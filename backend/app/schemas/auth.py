"""Auth request/response schemas with password strength validation."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.user import UserRead

PASSWORD_MIN_LENGTH = 8


def validate_password_strength(value: str) -> str:
    if len(value) < PASSWORD_MIN_LENGTH:
        raise ValueError(
            f"Password must be at least {PASSWORD_MIN_LENGTH} characters long"
        )
    if not any(c.isalpha() for c in value):
        raise ValueError("Password must contain at least one letter")
    if not any(c.isdigit() for c in value):
        raise ValueError("Password must contain at least one number")
    return value


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=PASSWORD_MIN_LENGTH, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)

    _check_password = field_validator("password")(validate_password_strength)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until the access token expires
    user: UserRead


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=PASSWORD_MIN_LENGTH, max_length=128)

    _check_password = field_validator("new_password")(validate_password_strength)


class MessageResponse(BaseModel):
    detail: str
