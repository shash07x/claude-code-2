# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**TeamSync** — an AI-powered project management SaaS (Jira/Linear/Trello space) for startups & SMBs. The repo currently contains the **authentication vertical slice** plus product-planning docs. Target stack (per `docs/` and `AUTH_IMPLEMENTATION_PLAN.md`): Next.js frontend + FastAPI/PostgreSQL backend, with future Redis/Celery for async + AI jobs.

Two independent apps, run/developed separately:
- `backend/` — FastAPI auth API (Python 3.13)
- `frontend/` — Next.js 14 App Router UI (TypeScript)

## Commands

### Backend (`cd backend`)
A virtualenv already exists at `backend/.venv`. Use its interpreter directly (Windows paths):
```bash
./.venv/Scripts/python.exe -m pytest               # run all tests (in-memory SQLite, no DB needed)
./.venv/Scripts/python.exe -m pytest tests/test_auth.py::test_login_success   # single test
./.venv/Scripts/python.exe -m uvicorn app.main:app --reload   # dev server :8000 (docs at /docs)
pip install -r requirements-dev.txt                # full deps incl. test tooling (PyJWT, bcrypt, httpx…)
docker compose up -d                               # Postgres on :5432 (only when using Postgres, not for tests)
```

### Frontend (`cd frontend`)
```bash
npm run dev      # dev server :3000
npm run build    # production build — ALSO does the full TypeScript type-check; use this to verify types
npm run lint
```
There is no separate `tsc` script; **`npm run build` is the type-check gate.**

## Architecture

### Backend: layered, async, token-based auth
Request flow: **route → service → model**, with security/token helpers underneath. Keep routes thin; business logic lives in services.

- `app/core/` — cross-cutting foundation:
  - `config.py` — `pydantic-settings` `Settings` (singleton via `get_settings()`). **`DATABASE_URL` defaults to a local SQLite file** so the app runs with zero setup; switch to Postgres via env. Cookie/JWT/CORS knobs live here.
  - `database.py` — async SQLAlchemy engine + `AsyncSessionLocal`, declarative `Base`, `TimestampMixin`, the `get_db` FastAPI dependency, and `create_all()`. SQLite gets a `StaticPool` so in-memory test DBs persist across connections.
  - `security.py` — bcrypt hashing (72-byte-safe) + token helpers. **Two token types:** stateless **access JWTs** (`create_/decode_access_token`, PyJWT, `type=access` claim) and **opaque** refresh/reset tokens (`generate_opaque_token` returns `(raw, sha256_hash)` — only the hash is ever stored).
- `app/models/` — `User`, `RefreshToken`, `PasswordResetToken`. Importing `app.models` registers all tables on `Base.metadata` (relied on by `create_all`).
- `app/services/auth_service.py` — all auth logic: user CRUD, `authenticate` (with dummy-verify timing defense), refresh-token create/rotate/revoke, password-reset issue/consume. Emails are normalized lowercase via `normalize_email`.
- `app/services/email.py` — `EmailSender` interface; `ConsoleEmailSender` logs in dev. Injected as a FastAPI dependency (`get_email_sender`) so it's overridable in tests/prod.
- `app/api/deps.py` — **`get_current_user` is the protected-route guard.** Add `Depends(get_current_user)` to any route to require a valid Bearer access token.
- `app/api/routes/auth.py` — the seven endpoints under `/api/v1/auth` (signup, login, refresh, logout, password-reset/request, password-reset/confirm, me).
- `app/main.py` — app factory, CORS (`allow_credentials=True` so the browser sends the refresh cookie), router wiring, and a `lifespan` that calls `create_all()` on startup.

**Auth model (important):** access JWT (15 min) in `Authorization: Bearer …`; refresh token is opaque, stored hashed in `refresh_tokens`, delivered as an **httpOnly cookie scoped to `/api/v1/auth`** (7 days). `/refresh` **rotates** (revokes old, issues new). Logout and password-reset revoke sessions server-side — this is why refresh tokens are DB-backed rather than pure JWT.

### Frontend: in-memory access token + cookie refresh
- `lib/api.ts` — single API client. Access token kept **in memory only** (not `localStorage`). `apiRequest` attaches the Bearer header, sends `credentials: "include"`, and on a 401 transparently calls `/auth/refresh` once and retries. `authApi` wraps the endpoints.
- `lib/auth-context.tsx` — `AuthProvider` restores the session on mount via `tryRefresh()`; exposes `useAuth()` with `{user, status, login, signup, logout}`. `status` is `loading | authenticated | unauthenticated`.
- `components/protected-route.tsx` — **route protection is client-side.** The refresh cookie is httpOnly and origin-scoped to the API, so Next.js middleware can't read it cross-origin; the dashboard redirects to `/login` unless authenticated. (Middleware/edge gating would require a same-origin BFF — noted as a future enhancement, not present.)
- `app/*/page.tsx` — login, signup, forgot-password, reset-password (reads `?token=` via `useSearchParams`, wrapped in `Suspense`), dashboard (wrapped in `ProtectedRoute`).

## Conventions & gotchas
- **Tests use SQLite, prod uses Postgres.** Tests (`tests/conftest.py`) build a fresh in-memory DB per test and override `get_db` + `get_email_sender` via `app.dependency_overrides`; the ASGI client does **not** run the lifespan, so the app's real engine is never touched. Don't assume Postgres-only SQL.
- The startup `create_all()` is a dev convenience; **production schema should be managed with Alembic** (not yet set up).
- Password rules (≥8 chars, letter + number) live in `app/schemas/auth.py::validate_password_strength` — reuse it, don't duplicate.
- Password-reset request always returns 202 and login errors are generic — intentional, to avoid account enumeration. Preserve this.
- `SECRET_KEY` defaults to a dev placeholder; it must be overridden in production (config now **raises** if the dev key is used when `ENVIRONMENT=production` — see **Security hardening**).
- Tests patch `settings.COOKIE_SECURE = False` in `conftest.py` so httpx sends cookies over `http://test`. **Don't remove it** — the refresh-rotation and logout tests break otherwise (Secure cookies are dropped on plain HTTP).
- Frontend pins `next@14.2.35` (patched). Avoid `npm audit fix --force` — it pushes a breaking major (Next 16).

## Notification Center

### Backend additions
- `app/models/notification.py` — `Notification` model (`type`, `title`, `body`, `resource_type`, `resource_id`, `is_read`, `read_at`). `type` stored as `String(50)` (not a DB enum) for SQLite/Postgres portability. Added `notifications` relationship to `User`.
- `app/schemas/notification.py` — `NotificationRead`, `NotificationListResponse` (items + total + unread_count), `UnreadCountResponse`.
- `app/services/notification_service.py` — `create_notification`, `get_notifications` (paginated, returns tuple `(items, total)`), `get_unread_count`, `mark_read` (idempotent — won't overwrite `read_at`), `mark_all_read` (uses `UPDATE … RETURNING`), `delete_notification`.
- `app/api/routes/notifications.py` — 5 endpoints under `/api/v1/notifications`: `GET /`, `GET /unread-count`, `POST /{id}/read`, `POST /read-all`, `DELETE /{id}`. All require `get_current_user`.
- Tests in `tests/test_notifications.py` use the `db_session` fixture (added to `conftest.py`) to seed data directly via the service layer — no public create endpoint needed.

### Frontend additions
- `Notification`, `NotificationListResponse`, `UnreadCountResponse` interfaces + `notificationsApi` object in `lib/api.ts`.
- `components/notification-panel.tsx` — bell icon with unread badge, dropdown panel: polling unread count every 30s, loads list on open, mark-single-read on click, mark-all-read button, per-item delete. No external icon library (inline SVG).
- Notification panel sits in the dashboard header next to the logout button.
- CSS for the panel is at the bottom of `app/globals.css`.

## Sprint Board (Kanban)

The first piece of the core domain. **Issues are scoped per-user** (`issues.user_id`), like notifications. Issues also carry a **nullable** `workspace_id` (see **Workspaces**), but the board still groups by `(user_id, status)` only — it does **not** yet filter by workspace, so it remains effectively a personal Kanban. The ordering model below is unaffected by workspace scoping.

### Ordering model (important)
Every issue has an integer `position` that is **0-based and contiguous within its `(user_id, status)` column**. The four columns are fixed: `backlog | in_progress | review | done` (order + labels live in `app/schemas/issue.py::BOARD_COLUMNS` / `COLUMN_LABELS` — the single source of truth, mirrored on the frontend).
- `issue_service.move_issue(issue, new_status, new_index)` rebuilds the target column excluding the moved card, inserts at `new_index` (clamped), and re-indexes `0..n`; if the column changed it re-indexes the source column too. `create_issue` appends; `delete_issue` re-indexes the column to close the gap.
- **`new_index` semantics:** the index within the target column's list **excluding the dragged card**. The frontend computes exactly this, so there's no off-by-one across the wire.

### Backend
- `app/models/issue.py` — `Issue` (`title`, `description`, `status`, `position`, `priority`, nullable `workspace_id` FK→workspaces `ON DELETE SET NULL`). `status`/`priority` are `String` (not DB enums) for portability. `issues` relationship added to `User`; `workspace` relationship to `Workspace`.
- `app/services/issue_service.py` — board/create/update/move/delete (see ordering model above).
- `app/api/routes/issues.py` — `/api/v1/issues`: `GET /board` (grouped into the 4 columns), `POST /`, `PATCH /{id}`, `PATCH /{id}/move` (persists a drop), `DELETE /{id}`. All require `get_current_user` and enforce ownership (404 otherwise). **Note:** update/move routes call `await db.refresh(issue)` after commit — the `onupdate` `updated_at` is server-generated and would otherwise fail an async lazy-load during serialization.
- `tests/test_issues.py` — 20 tests covering append, grouping/order, move within & across columns, contiguous re-indexing, clamp, validation, and ownership isolation (incl. a cross-user PATCH ownership test).

### Frontend
- `Issue` / `BoardColumn` / `BoardResponse` types + `issuesApi` (board, create, update, move, delete) in `lib/api.ts`.
- `components/sprint-board.tsx` — **native HTML5 drag-and-drop (no DnD library)**. `applyLocalMove` does an optimistic update, then `issuesApi.move` persists; on failure it rolls back and reloads. Drop index is computed from pointer Y vs. card midpoints, skipping the dragged card. Includes per-column add-card input, delete, priority badges, column highlight on drag-over.
- `app/board/page.tsx` — protected `/board` page; linked from the dashboard. Board CSS is at the bottom of `app/globals.css`.

## CSV Bulk Importer

Imports Jira / Linear / Trello CSV exports as issues onto the per-user board. **No new model** — it maps each external row onto the existing `Issue` (title/description/status/priority) and reuses `issue_service.create_issue` so column ordering + per-user scoping stay consistent. Because `Issue` only has those four fields, every other column is reported as **unmapped (dropped)** rather than silently lost. Commits may optionally target a workspace: `commit_import` accepts a `workspace_id` that is threaded into each `create_issue` (it is a commit parameter, not a CSV column).

### Per-format adapters (independent workstreams)
- `app/services/importers/` — one module per source sharing a `FormatAdapter` base (`base.py`): `jira.py`, `linear.py`, `trello.py`, plus `__init__.py` (registry + `get_adapter` / `detect_adapter`).
  - Adapters work on **lower-cased, stripped header keys** (the service normalizes rows before mapping). Generic adapters are column-driven (`title_field`, `status_map`, `priority_map`, …); **Trello overrides** `_map_status` (substring-match on the free-text *list name*) and `_map_priority` (keyword-match on *labels* — Trello has no priority column).
  - **Auto-detection order matters:** Jira (`Summary`) and Trello (`Card Name`) are checked before Linear (generic `Title`). `mapped_fields()` drives unmapped-column reporting.
- `app/services/import_service.py` — orchestration: `_parse_csv` (BOM-stripped `csv.DictReader`), `_map_rows` (skips blank lines, keeps 1-based CSV line numbers), `_validate` (generic rules: title required → row invalid; title/description length-truncate → warning). `build_preview` is a pure dry-run (no writes); `commit_import` persists only valid rows. Raises `CsvImportError` (→ 422); **not** the builtin `ImportError`.
- `app/api/routes/imports.py` — `/api/v1/imports`: `POST /preview` (dry-run), `POST /commit` (persists, then `db.commit()`). Both require `get_current_user`. Input is raw CSV **text in a JSON body** (frontend reads the file), so no multipart handling. `ImportCommitRequest` accepts an optional `workspace_id`; `/commit` validates the caller owns that workspace (404 otherwise) before persisting.
- `tests/test_imports.py` — 23 tests: per-format mapping, auto-detect + explicit-source override, undetectable→422, validation/truncation/unmapped reporting, preview-doesn't-write, commit appends+reindexes, skips invalid, per-user isolation, and per-importer `workspace_id` writes.

### Frontend
- `ImportSource` / `ImportRowPreview` / `ImportPreviewResponse` / `ImportCommitResponse` types + `importsApi` (preview, commit) in `lib/api.ts`.
- `components/csv-importer.tsx` — file upload (FileReader → text) or paste, format select (auto/jira/linear/trello), **preview-before-import** table (per-row status/priority badges + error/warning notes, dropped-columns banner), then commit. `app/import/page.tsx` is the protected `/import` page, linked from the dashboard and the board header. Importer CSS is at the bottom of `app/globals.css`.

## Workspaces

The top-level multi-tenant scope. **Owner-only authorization — there is no membership table yet**, so a workspace is reachable only by its creator.

- `app/models/workspace.py` — `Workspace` (`name`, `owner_id` FK→users `ON DELETE CASCADE`). `owned_workspaces` relationship added to `User`; `issues` relationship to `Issue`.
- `app/schemas/workspace.py` — `WorkspaceCreate` (`name` 1–100 chars), `WorkspaceRead`.
- `app/services/workspace_service.py` — `create_workspace`, `get_workspace`.
- `app/api/routes/workspaces.py` — `/api/v1/workspaces`: `POST /` (201), `GET /{id}` (404 if the caller isn't the owner). Both require `get_current_user`.
- `Issue` gained a **nullable** `workspace_id` FK (`ON DELETE SET NULL`) for backward compatibility; `issue_service.create_issue` accepts an optional `workspace_id`. Existing per-user issues keep `workspace_id = NULL`.

## Security hardening

- **Rate limiting** (`slowapi`): shared limiter in `app/core/limiter.py`, wired in `main.py` (`app.state.limiter` + 429 handler). Auth limits: signup `10/minute`, login `5/minute`, password-reset-request `3/minute`.
- **Security-headers middleware** (`main.py`): `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy` on every response; `Strict-Transport-Security` added **in production only**.
- **Cookies & config** (`app/core/config.py`): `COOKIE_SECURE` defaults to `True` (HTTPS-only); config **raises** if `SECRET_KEY` is the dev placeholder under `ENVIRONMENT=production`, and enforces `COOKIE_SAMESITE=none ⇒ COOKIE_SECURE=true`. New knobs: `ENVIRONMENT` (development|test|production), `CORS_ORIGINS`.
- CORS is restricted via `CORS_ORIGINS` (still `allow_credentials=True` for the refresh cookie).

## Status
Built so far: auth + Notification Center + Sprint Board (Kanban) + CSV Bulk Importer + Workspaces. **79 backend tests passing** (17 auth + 19 notifications + 20 issues + 23 imports). Frontend production build clean (11 routes). Workspace model now exists (owner-only, no membership table yet); issues carry a nullable `workspace_id`. Project hierarchy and workspace membership are still not built. Product docs in `docs/` are planned but only `docs/README.md` exists.
