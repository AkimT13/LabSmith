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
        # Auto-create user from JWT claims (webhook may not have fired yet)
        user = User(
            clerk_user_id=clerk_user_id,
            email=payload.get("email", f"{clerk_user_id}@clerk.placeholder"),
            display_name=payload.get("name"),
            avatar_url=payload.get("image_url"),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return user
