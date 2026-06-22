"""TeamSync API application entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.routes import auth, imports, issues, notifications, workspaces
from app.core.config import settings
from app.core.database import create_all
from app.core.limiter import limiter  # C2: shared limiter imported by routes too

logging.basicConfig(level=logging.INFO)

_IS_PROD = settings.ENVIRONMENT == "production"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Bootstrap tables on startup. For Postgres in production, prefer Alembic
    # migrations; create_all is idempotent and convenient for dev/SQLite.
    await create_all()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    # H3: hide API docs in production — no interactive schema for attackers.
    openapi_url=None if _IS_PROD else f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url=None if _IS_PROD else "/docs",
    redoc_url=None if _IS_PROD else "/redoc",
    lifespan=lifespan,
)

# C2: attach the limiter state and its 429 handler.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,  # required so the browser sends the refresh cookie
    # M2: restrict to the methods and headers the API actually uses.
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# M1: Minimal security headers on every response.
@app.middleware("http")
async def security_headers(request: Request, call_next) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if _IS_PROD:
        response.headers["Strict-Transport-Security"] = (
            "max-age=63072000; includeSubDomains"
        )
    return response


app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(notifications.router, prefix=settings.API_V1_PREFIX)
app.include_router(issues.router, prefix=settings.API_V1_PREFIX)
app.include_router(imports.router, prefix=settings.API_V1_PREFIX)
app.include_router(workspaces.router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.PROJECT_NAME}
