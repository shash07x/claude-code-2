# TeamSync Backend (FastAPI)

Authentication API: signup, login, logout, password reset, and protected routes.

## Stack
FastAPI · SQLAlchemy 2 (async) · PostgreSQL (prod) / SQLite (dev & tests) · PyJWT · bcrypt.

## Quick start

```bash
cd backend
python -m venv .venv
# Windows:  .venv\Scripts\activate     |  macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt        # full runtime incl. Postgres driver
cp .env.example .env                    # then set a real SECRET_KEY

uvicorn app.main:app --reload           # http://localhost:8000  (docs at /docs)
```

By default it uses a local **SQLite** file (`teamsync.db`) — zero setup. Tables are
auto-created on startup.

### Using PostgreSQL
```bash
docker compose up -d                    # starts Postgres on :5432
# in .env:
# DATABASE_URL=postgresql+asyncpg://teamsync:teamsync@localhost:5432/teamsync
```
In production, manage schema with Alembic rather than the startup `create_all`.

## Endpoints (`/api/v1/auth`)
| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/signup` | — | Register + auto-login |
| POST | `/login` | — | Log in |
| POST | `/refresh` | refresh cookie | New access token (rotates refresh) |
| POST | `/logout` | refresh cookie | Revoke session |
| POST | `/password-reset/request` | — | Email a reset link (console in dev) |
| POST | `/password-reset/confirm` | — | Set new password |
| GET | `/me` | Bearer | **Protected** — current user |

- **Access token**: JWT in `Authorization: Bearer …` (15 min).
- **Refresh token**: opaque, stored hashed, delivered as an httpOnly cookie (7 days),
  revocable on logout / password reset.

## Tests
```bash
pip install -r requirements-dev.txt
pytest                # runs against in-memory SQLite — no DB server needed
```
The suite (`tests/test_auth.py`) covers the full happy path plus failure cases
(duplicate email, bad credentials, missing/invalid token, refresh rotation &
revocation, single-use reset tokens). **17 tests, all passing.**

## Manual smoke test (with the server running)
```bash
curl -X POST localhost:8000/api/v1/auth/signup \
  -H 'Content-Type: application/json' \
  -d '{"email":"a@b.com","password":"Password123","full_name":"A B"}'
# → returns access_token; copy it:
curl localhost:8000/api/v1/auth/me -H 'Authorization: Bearer <token>'
```

## Layout
```
app/
  core/        config, async DB engine, security (hashing + tokens)
  models/      User, RefreshToken, PasswordResetToken
  schemas/     Pydantic request/response models
  services/    auth_service (business logic), email (console sender)
  api/         deps (get_current_user guard), routes/auth.py
  main.py      app factory, CORS, router wiring
tests/         pytest suite (SQLite)
```
