"""Shared API dependencies, including the protected-route guard."""
from __future__ import annotations

import uuid

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.services import auth_service

# auto_error=False so we can return a consistent 401 with a WWW-Authenticate header.
_bearer_scheme = HTTPBearer(auto_error=False)

_credentials_exc = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the authenticated user from a Bearer access token.

    Add ``user: User = Depends(get_current_user)`` to any route to protect it.
    """
    if credentials is None or not credentials.credentials:
        raise _credentials_exc
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise _credentials_exc

    user = await auth_service.get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        raise _credentials_exc
    return user
