from __future__ import annotations

import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.clerk import get_current_user
from app.config import settings
from app.database import get_db
from app.models.user import User
from app.schemas.auth import UserResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.post("/webhook")
async def clerk_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    """Handle Clerk webhook events for user sync."""
    body = await request.body()

    # Verify webhook signature if secret is configured
    if settings.clerk_webhook_secret:
        svix_signature = request.headers.get("svix-signature", "")
        svix_id = request.headers.get("svix-id", "")
        svix_timestamp = request.headers.get("svix-timestamp", "")

        if not svix_signature or not svix_id or not svix_timestamp:
            raise HTTPException(status_code=400, detail="Missing webhook signature headers")

        signed_content = f"{svix_id}.{svix_timestamp}.{body.decode()}"
        # Clerk uses whsec_ prefix for webhook secrets
        secret = settings.clerk_webhook_secret
        if secret.startswith("whsec_"):
            secret = secret[6:]

        # Base64-decode the secret
        import base64

        secret_bytes = base64.b64decode(secret)
        expected_signature = base64.b64encode(
            hmac.new(secret_bytes, signed_content.encode(), hashlib.sha256).digest()
        ).decode()

        # svix-signature can contain multiple signatures separated by spaces
        signatures = [s.split(",", 1)[-1] for s in svix_signature.split(" ")]
        if expected_signature not in signatures:
            raise HTTPException(status_code=400, detail="Invalid webhook signature")

    payload = json.loads(body)
    event_type = payload.get("type")
    data = payload.get("data", {})

    if event_type == "user.created":
        await _upsert_user(db, data)
    elif event_type == "user.updated":
        await _upsert_user(db, data)
    elif event_type == "user.deleted":
        clerk_id = data.get("id")
        if clerk_id:
            result = await db.execute(select(User).where(User.clerk_user_id == clerk_id))
            user = result.scalar_one_or_none()
            if user:
                await db.delete(user)
                await db.commit()

    return {"status": "ok"}


async def _upsert_user(db: AsyncSession, data: dict) -> User:
    """Create or update a user from Clerk webhook data."""
    clerk_id = data.get("id")
    email = None
    for addr in data.get("email_addresses", []):
        if addr.get("id") == data.get("primary_email_address_id"):
            email = addr.get("email_address")
            break
    if not email:
        emails = data.get("email_addresses", [])
        email = emails[0]["email_address"] if emails else f"{clerk_id}@clerk.placeholder"

    display_name = " ".join(
        filter(None, [data.get("first_name"), data.get("last_name")])
    ) or None
    avatar_url = data.get("image_url")

    result = await db.execute(select(User).where(User.clerk_user_id == clerk_id))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            clerk_user_id=clerk_id,
            email=email,
            display_name=display_name,
            avatar_url=avatar_url,
        )
        db.add(user)
    else:
        user.email = email
        user.display_name = display_name
        user.avatar_url = avatar_url

    await db.commit()
    await db.refresh(user)
    return user
