from __future__ import annotations

import logging

import httpx
from fastapi import Depends, HTTPException, Request
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User

logger = logging.getLogger(__name__)

_jwks_cache: dict | None = None


def _get_jwks_url() -> str:
    """Resolve the JWKS URL — use explicit setting or fall back to Clerk Backend API."""
    if settings.clerk_jwks_url:
        return settings.clerk_jwks_url
    # Clerk Backend API endpoint (requires secret key in header)
    return "https://api.clerk.com/v1/jwks"


async def _get_jwks() -> dict:
    """Fetch Clerk's JWKS (cached in-process)."""
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache

    url = _get_jwks_url()
    headers = {}
    # Clerk Backend API requires Authorization header with secret key
    if "api.clerk.com" in url and settings.clerk_secret_key:
        headers["Authorization"] = f"Bearer {settings.clerk_secret_key}"

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        _jwks_cache = resp.json()
        return _jwks_cache


def _extract_bearer_token(request: Request) -> str:
    """Extract the Bearer token from the Authorization header."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    return auth_header[7:]


async def verify_clerk_token(request: Request) -> dict:
    """Verify a Clerk JWT and return the decoded payload."""
    token = _extract_bearer_token(request)

    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as exc:
        logger.warning("Malformed JWT header: %s", exc)
        raise HTTPException(status_code=401, detail="Malformed token") from exc

    try:
        jwks = await _get_jwks()
    except Exception as exc:
        logger.error("Failed to fetch JWKS: %s", exc)
        raise HTTPException(status_code=503, detail="Auth service unavailable") from exc

    try:
        kid = unverified_header.get("kid")
        rsa_key = None
        for key in jwks.get("keys", []):
            if key["kid"] == kid:
                rsa_key = key
                break

        if rsa_key is None:
            # Invalidate cache and retry once
            global _jwks_cache
            _jwks_cache = None
            try:
                jwks = await _get_jwks()
            except Exception as exc:
                logger.error("Failed to re-fetch JWKS: %s", exc)
                raise HTTPException(status_code=503, detail="Auth service unavailable") from exc
            for key in jwks.get("keys", []):
                if key["kid"] == kid:
                    rsa_key = key
                    break

        if rsa_key is None:
            raise HTTPException(status_code=401, detail="Unable to find appropriate signing key")

        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
        return payload

    except HTTPException:
        raise
    except JWTError as exc:
        logger.warning("JWT verification failed: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid token") from exc


async def _fetch_clerk_user_profile(clerk_user_id: str) -> dict | None:
    """Fetch the real user profile from Clerk's Backend API.

    Returns None if the secret key is not configured or the request fails — callers
    should fall back to JWT claims / placeholders rather than blocking sign-in.
    """
    if not settings.clerk_secret_key:
        return None

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"https://api.clerk.com/v1/users/{clerk_user_id}",
                headers={"Authorization": f"Bearer {settings.clerk_secret_key}"},
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:  # noqa: BLE001 — non-fatal best-effort fetch
        logger.warning("Could not fetch Clerk user %s: %s", clerk_user_id, exc)
        return None


def _profile_from_clerk_payload(data: dict, clerk_user_id: str) -> dict:
    """Extract email/display_name/avatar_url from a Clerk Backend API user payload."""
    primary_email_id = data.get("primary_email_address_id")
    email = None
    for addr in data.get("email_addresses", []) or []:
        if addr.get("id") == primary_email_id:
            email = addr.get("email_address")
            break
    if email is None:
        emails = data.get("email_addresses") or []
        email = emails[0]["email_address"] if emails else None

    display_name = (
        " ".join(filter(None, [data.get("first_name"), data.get("last_name")])).strip()
        or data.get("username")
        or None
    )

    return {
        "email": email or f"{clerk_user_id}@clerk.placeholder",
        "display_name": display_name,
        "avatar_url": data.get("image_url") or data.get("profile_image_url"),
    }


def _profile_from_jwt(payload: dict, clerk_user_id: str) -> dict:
    """Best-effort profile from JWT claims when the Backend API is unavailable."""
    return {
        "email": payload.get("email") or f"{clerk_user_id}@clerk.placeholder",
        "display_name": payload.get("name"),
        "avatar_url": payload.get("image_url") or payload.get("picture"),
    }


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Verify JWT and return the corresponding local User, upserting if needed."""
    payload = await verify_clerk_token(request)
    clerk_user_id = payload.get("sub")
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Token missing subject claim")

    result = await db.execute(select(User).where(User.clerk_user_id == clerk_user_id))
    user = result.scalar_one_or_none()

    if user is None:
        # Auto-create user. Prefer the Clerk Backend API for real profile data,
        # since most Clerk JWTs don't include email/name claims by default.
        clerk_profile = await _fetch_clerk_user_profile(clerk_user_id)
        profile = (
            _profile_from_clerk_payload(clerk_profile, clerk_user_id)
            if clerk_profile
            else _profile_from_jwt(payload, clerk_user_id)
        )
        user = User(
            clerk_user_id=clerk_user_id,
            email=profile["email"],
            display_name=profile["display_name"],
            avatar_url=profile["avatar_url"],
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    elif user.email.endswith("@clerk.placeholder"):
        # Existing user has placeholder data — try once to backfill from Clerk.
        clerk_profile = await _fetch_clerk_user_profile(clerk_user_id)
        if clerk_profile:
            profile = _profile_from_clerk_payload(clerk_profile, clerk_user_id)
            if not profile["email"].endswith("@clerk.placeholder"):
                user.email = profile["email"]
                user.display_name = profile["display_name"]
                user.avatar_url = profile["avatar_url"]
                await db.commit()
                await db.refresh(user)

    return user
