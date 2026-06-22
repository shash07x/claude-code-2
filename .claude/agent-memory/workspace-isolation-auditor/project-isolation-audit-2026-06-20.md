---
name: teamsync-isolation-audit-jun-2026
description: First full workspace isolation audit of TeamSync backend — findings, patterns, and migration readiness as of 2026-06-20
metadata:
  type: project
---

TeamSync completed its first workspace isolation audit on 2026-06-20. Overall posture is SAFE for the current single-tenant-per-user architecture, with no HIGH or CRITICAL findings. All queries are scoped by `user_id`; no `workspace_id` column or RLS exists yet.

**Key findings recorded:**

- `issues`, `notifications`, `refresh_tokens`, `password_reset_tokens` tables all carry `user_id` FK with `ondelete=CASCADE`. Isolation is application-layer only (no RLS).
- Every service function that touches issues or notifications requires `user_id` as a parameter and filters by it in every SELECT, UPDATE, DELETE.
- The `_get_owned_issue` helper in `issues.py` is the central ownership-check pattern: looks up by `(issue_id, user_id)` and returns 404 on mismatch — correctly prevents enumeration.
- `prune_expired_tokens` in `auth_service.py:142` does a bulk UPDATE with no `user_id` filter — intentional; it's a maintenance function on token-scoped (not user-data) rows. Acceptable.
- `get_active_refresh_token` in `auth_service.py:101` looks up only by `token_hash`, no `user_id`. This is secure because the token hash is a 256-bit opaque token — unguessable. The user is then derived from `token.user_id`. No isolation risk.
- `build_preview` in `import_service.py` is a pure dry-run with zero DB writes. No user_id needed in the function itself; the route guard ensures authentication.
- `/health` endpoint is intentionally public — exposes only `{"status": "ok"}`, no tenant data.
- Docs (`/docs`, `/redoc`, `/openapi.json`) are disabled in production via `openapi_url=None`.

**Test coverage for isolation:**
- `test_board_only_shows_own_issues` — GET /board cross-user isolation confirmed.
- `test_cannot_move_another_users_issue` — PATCH /{id}/move cross-user 404 confirmed.
- `test_cannot_delete_another_users_issue` — DELETE /{id} cross-user 404 confirmed.
- `test_mark_read_other_users_notification` — POST /{id}/read cross-user 404 confirmed.
- `test_mark_all_read_only_affects_current_user` — bulk UPDATE cross-user isolation confirmed.
- `test_delete_other_users_notification` — DELETE /{id} cross-user 404 confirmed.
- `test_commit_isolated_per_user` — CSV import cross-user board isolation confirmed.
- GAP: No test for `PATCH /{issue_id}` (update) with another user's token.

**Why:** Issues are intentionally per-user. Workspace/project hierarchy is a stated future enhancement. All PENDING MIGRATION findings (user_id-only filters) are by design, not bugs.
**How to apply:** When workspace_id is introduced, update every `Issue` and `Notification` query site to AND in `workspace_id`. The `_get_owned_issue` helper and `get_notifications`/`get_unread_count`/`mark_read`/`mark_all_read`/`delete_notification` service functions are the primary update targets. See [[teamsync-workspace-migration-readiness]].
