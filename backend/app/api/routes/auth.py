"""Authentication routes: signup, login, refresh, logout, password reset, me."""
from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    MessageResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
    SignupRequest,
    TokenResponse,
)
from app.schemas.user import UserRead
from app.services import auth_service
from app.services.email import (
    EmailSender,
    build_password_reset_email,
    get_email_sender,
)

router = APIRouter(prefix="/auth", tags=["auth"])


# --- helpers -----------------------------------------------------------------

def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=raw_token,
        max_age=settings.refresh_cookie_max_age,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        path=f"{settings.API_V1_PREFIX}/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        domain=settings.COOKIE_DOMAIN,
        path=f"{settings.API_V1_PREFIX}/auth",
    )


def _client_meta(request: Request) -> tuple[str | None, str | None]:
    ua = request.headers.get("user-agent")
    ip = request.client.host if request.client else None
    return ua, ip


def _token_response(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserRead.model_validate(user),
    )


# --- routes ------------------------------------------------------------------

@router.post(
    "/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
async def signup(
    payload: SignupRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    existing = await auth_service.get_user_by_email(db, payload.email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )
    user = await auth_service.create_user(
        db,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
    )
    ua, ip = _client_meta(request)
    raw_refresh = await auth_service.create_refresh_token(
        db, user=user, user_agent=ua, ip_address=ip
    )
    await db.commit()
    await db.refresh(user)
    _set_refresh_cookie(response, raw_refresh)
    return _token_response(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    user = await auth_service.authenticate(
        db, email=payload.email, password=payload.password
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    ua, ip = _client_meta(request)
    raw_refresh = await auth_service.create_refresh_token(
        db, user=user, user_agent=ua, ip_address=ip
    )
    await db.commit()
    _set_refresh_cookie(response, raw_refresh)
    return _token_response(user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    raw = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token",
        )
    token = await auth_service.get_active_refresh_token(db, raw)
    if token is None:
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    ua, ip = _client_meta(request)
    new_raw = await auth_service.rotate_refresh_token(
        db, old_token=token, user_agent=ua, ip_address=ip
    )
    user = await auth_service.get_user_by_id(db, token.user_id)
    if user is None or not user.is_active:
        await db.commit()
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    await db.commit()
    _set_refresh_cookie(response, new_raw)
    return _token_response(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> Response:
    raw = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if raw:
        token = await auth_service.get_active_refresh_token(db, raw)
        if token is not None:
            await auth_service.revoke_refresh_token(db, token)
            await db.commit()
    out = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_refresh_cookie(out)
    return out


@router.post(
    "/password-reset/request",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_password_reset(
    payload: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
    email_sender: EmailSender = Depends(get_email_sender),
) -> MessageResponse:
    # Always return the same response to avoid leaking which emails are registered.
    user = await auth_service.get_user_by_email(db, payload.email)
    if user is not None and user.is_active:
        raw = await auth_service.create_password_reset_token(db, user)
        await db.commit()
        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={raw}"
        await email_sender.send(
            build_password_reset_email(user.email, reset_link)
        )
    return MessageResponse(
        detail="If an account exists for that email, a reset link has been sent."
    )


@router.post("/password-reset/confirm", response_model=MessageResponse)
async def confirm_password_reset(
    payload: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    token = await auth_service.consume_password_reset_token(db, payload.token)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )
    await auth_service.reset_password(
        db, token=token, new_password=payload.new_password
    )
    await db.commit()
    return MessageResponse(
        detail="Password updated. Please log in with your new password."
    )


@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
