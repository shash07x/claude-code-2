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

# M3: Pre-computed dummy hash so the timing of a failed login (unknown email) is
# always one bcrypt verify, not one hash + one verify on a fresh random salt.
_DUMMY_HASH = hash_password("dummy-placeholder-xyzzy-never-matches-real-user")


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
    # M3: Always run exactly one bcrypt verify so response time doesn't reveal
    # whether the email exists (compare against pre-computed hash when no user).
    stored_hash = user.hashed_password if user else _DUMMY_HASH
    if not verify_password(password, stored_hash):
        return None
    if user is None or not user.is_active:
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
    now = _utcnow()
    await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    # L5: Also expire any outstanding password-reset tokens so a reset link
    # obtained before a password change can't be used after the fact.
    await db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=now)
    )


async def prune_expired_tokens(db: AsyncSession) -> None:
    """M4: Delete refresh + reset token rows that are fully expired and revoked.

    Call periodically (e.g. from a Celery beat task) to keep the tables bounded.
    """
    cutoff = _utcnow() - dt.timedelta(days=1)
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.expires_at < cutoff)
        .values(revoked_at=_utcnow())
        .execution_options(synchronize_session=False)
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
    # H5: explicit guard — assert is stripped by -O and would produce a
    # confusing AttributeError rather than a clean error.
    if user is None:
        raise ValueError(f"User {old_token.user_id} not found during token rotation")
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
    # H5: explicit guard — assert is stripped by -O.
    if user is None:
        raise ValueError(f"User {token.user_id} not found during password reset")
    user.hashed_password = hash_password(new_password)
    token.used_at = _utcnow()
    # Security: invalidate every existing session after a password change.
    await revoke_all_user_sessions(db, user.id)
    await db.flush()
