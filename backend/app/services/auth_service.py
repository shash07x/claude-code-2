"""Authentication business logic: users, sessions, password reset.

Kept separate from the HTTP layer so routes stay thin and the logic is testable.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    generate_opaque_token,
    hash_opaque_token,
    hash_password,
    verify_password,
)
from app.models.token import PasswordResetToken, RefreshToken
from app.models.user import User


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def normalize_email(email: str) -> str:
    return email.strip().lower()


# --- Users ---

async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(
        select(User).where(User.email == normalize_email(email))
    )
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await db.get(User, user_id)


async def create_user(
    db: AsyncSession, *, email: str, password: str, full_name: str | None
) -> User:
    user = User(
        email=normalize_email(email),
        hashed_password=hash_password(password),
        full_name=full_name,
    )
    db.add(user)
    await db.flush()
    return user


async def authenticate(
    db: AsyncSession, *, email: str, password: str
) -> User | None:
    user = await get_user_by_email(db, email)
    if user is None:
        # Run a dummy verify to keep timing roughly constant (reduce enumeration).
        verify_password(password, hash_password("dummy-password-123"))
        return None
    if not user.is_active or not verify_password(password, user.hashed_password):
        return None
    return user


# --- Refresh tokens (sessions) ---

async def create_refresh_token(
    db: AsyncSession,
    *,
    user: User,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> str:
    """Create a session row and return the RAW token (to put in the cookie)."""
    raw, token_hash = generate_opaque_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=_utcnow()
            + dt.timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            user_agent=(user_agent or "")[:400] or None,
            ip_address=ip_address,
        )
    )
    await db.flush()
    return raw


async def get_active_refresh_token(
    db: AsyncSession, raw_token: str
) -> RefreshToken | None:
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_opaque_token(raw_token)
        )
    )
    token = result.scalar_one_or_none()
    if token is None or not token.is_active:
        return None
    return token


async def revoke_refresh_token(db: AsyncSession, token: RefreshToken) -> None:
    token.revoked_at = _utcnow()
    await db.flush()


async def revoke_all_user_sessions(db: AsyncSession, user_id: uuid.UUID) -> None:
    await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=_utcnow())
    )


async def rotate_refresh_token(
    db: AsyncSession,
    *,
    old_token: RefreshToken,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> str:
    """Revoke the presented token and issue a fresh one for the same user."""
    await revoke_refresh_token(db, old_token)
    user = await get_user_by_id(db, old_token.user_id)
    assert user is not None
    return await create_refresh_token(
        db, user=user, user_agent=user_agent, ip_address=ip_address
    )


# --- Password reset ---

async def create_password_reset_token(db: AsyncSession, user: User) -> str:
    """Create a single-use reset token; returns the RAW token for the email link."""
    raw, token_hash = generate_opaque_token(num_bytes=32)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=_utcnow()
            + dt.timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES),
        )
    )
    await db.flush()
    return raw


async def consume_password_reset_token(
    db: AsyncSession, raw_token: str
) -> PasswordResetToken | None:
    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_opaque_token(raw_token)
        )
    )
    token = result.scalar_one_or_none()
    if token is None or not token.is_valid:
        return None
    return token


async def reset_password(
    db: AsyncSession, *, token: PasswordResetToken, new_password: str
) -> None:
    user = await get_user_by_id(db, token.user_id)
    assert user is not None
    user.hashed_password = hash_password(new_password)
    token.used_at = _utcnow()
    # Security: invalidate every existing session after a password change.
    await revoke_all_user_sessions(db, user.id)
    await db.flush()
