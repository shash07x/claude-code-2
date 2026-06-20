"""Password hashing and token (JWT + opaque refresh/reset) helpers."""
from __future__ import annotations

import datetime as dt
import hashlib
import secrets
import uuid

import bcrypt
import jwt

from app.core.config import settings

# bcrypt operates on the first 72 bytes only; encode + truncate defensively.
_BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    pw = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        pw = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
        return bcrypt.checkpw(pw, hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# --- Access tokens (stateless JWT) ---

def create_access_token(
    subject: str | uuid.UUID, expires_delta: dt.timedelta | None = None
) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    expire = now + (
        expires_delta
        or dt.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": str(subject),
        "type": "access",
        "iat": now,
        "exp": expire,
        "jti": secrets.token_urlsafe(8),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate an access JWT. Raises jwt.PyJWTError on failure."""
    payload = jwt.decode(
        token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
    )
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Not an access token")
    return payload


# --- Opaque tokens (refresh + password reset), stored hashed server-side ---

def generate_opaque_token(num_bytes: int = 48) -> tuple[str, str]:
    """Return (raw_token, sha256_hash). Only the hash is persisted."""
    raw = secrets.token_urlsafe(num_bytes)
    return raw, hash_opaque_token(raw)


def hash_opaque_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
