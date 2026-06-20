# TeamSync — Authentication Implementation Plan

## Goal
Implement production-grade authentication for TeamSync: **Signup, Login, Logout, Password Reset, and Protected Routes** — using the agreed stack (FastAPI + PostgreSQL backend, Next.js frontend).

## Token strategy (access + refresh)
- **Access token** — short-lived JWT (15 min), `HS256`, claims: `sub` (user id), `type=access`, `exp`, `iat`, `jti`. Sent by the client in the `Authorization: Bearer <token>` header. Stateless — validated by signature only.
- **Refresh token** — long-lived (7 days), **opaque random string** (not a JWT), stored **hashed** in the `refresh_tokens` table so it can be revoked. Delivered to the browser as an **httpOnly, SameSite cookie** so JS can't read it (mitigates XSS token theft).
- **Logout** = delete/revoke the refresh-token row + clear the cookie. Access token expires naturally (short TTL).
- **Refresh rotation** — each `/auth/refresh` issues a new access token and rotates the refresh token (old one revoked), limiting replay.

This gives us stateless fast checks (access JWT) **and** server-side revocation (refresh tokens), which a pure-JWT design can't do.

## Data model (new tables)
| Table | Key columns | Notes |
|-------|-------------|-------|
| `users` | `id` (UUID PK), `email` (unique, citext), `hashed_password`, `full_name`, `is_active`, `is_verified`, `created_at`, `updated_at` | Core identity. |
| `refresh_tokens` | `id`, `user_id` (FK), `token_hash` (unique), `expires_at`, `revoked_at`, `created_at`, `user_agent`, `ip` | One row per active session; revoke on logout / password reset. |
| `password_reset_tokens` | `id`, `user_id` (FK), `token_hash` (unique), `expires_at`, `used_at`, `created_at` | Single-use, 30-min expiry. |

(These align with the User/auth entities in `docs/05-database-design.md`.)

## Security helpers (`app/core/security.py`)
- `hash_password` / `verify_password` — **bcrypt** (with 72-byte-safe encoding).
- `create_access_token(user_id)` → signed JWT.
- `decode_access_token(token)` → claims or raises.
- `generate_refresh_token()` → `(raw, hash)`; only the hash is stored.
- `hash_token(raw)` — SHA-256 for refresh/reset token lookups (fast, deterministic, opaque tokens are high-entropy so SHA-256 is appropriate).

## Endpoints (`/api/v1/auth`)
| Method | Path | Body | Result |
|--------|------|------|--------|
| POST | `/signup` | `email, password, full_name` | Create user, auto-login: returns access token + sets refresh cookie. `409` if email taken. |
| POST | `/login` | `email, password` | Verify creds → access token + refresh cookie. `401` on bad creds. |
| POST | `/refresh` | _(refresh cookie)_ | New access token + rotated refresh cookie. `401` if missing/expired/revoked. |
| POST | `/logout` | _(refresh cookie)_ | Revoke refresh token, clear cookie. Always `204`. |
| POST | `/password-reset/request` | `email` | Always `202` (no user-enumeration). If user exists, create reset token + send email link. |
| POST | `/password-reset/confirm` | `token, new_password` | Validate token → set new password, revoke all sessions. `400` on bad/expired token. |
| GET | `/me` | _(Bearer access)_ | **Protected** — returns current user. `401` if unauthenticated. |

## Protected routes
- **Backend:** `get_current_user` FastAPI dependency decodes the Bearer access token, loads the active user, and injects it. Any route adds `user: User = Depends(get_current_user)` to require auth (returns `401` otherwise).
- **Frontend:** Next.js `middleware.ts` redirects unauthenticated users (no refresh cookie) away from protected paths (e.g. `/dashboard`) to `/login`; an `AuthProvider` holds the in-memory access token and silently refreshes on load.

## Password / input rules
- Password: min 8 chars, must contain letters + numbers (validated via Pydantic).
- Email validated via `EmailStr`.
- Generic error messages on login + reset to avoid account enumeration.

## Email
- `EmailSender` interface with a **`ConsoleEmailSender`** (logs the reset link) for dev. SMTP/provider implementation plugs in later behind the same interface (Celery task in production).

## Testing & verification
- **Backend:** `pytest` suite runs against **SQLite (aiosqlite)** so it needs no DB server. Covers: signup → login → `/me` → refresh → logout → reset flow, plus failure cases (dup email, bad creds, expired/used reset token, accessing protected route without/with token). Run: `pytest`.
- **Manual / prod:** `docker compose up` (Postgres) + `uvicorn app.main:app --reload`; exercise via the Next.js UI or curl.

## Out of scope (future)
Email verification flow, OAuth/SSO, MFA, rate limiting (Redis), refresh-token device management UI — noted in the roadmap, not built now.
