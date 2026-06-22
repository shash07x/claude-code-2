---
name: teamsync-isolation-audit-workspace-commit
description: Audit of workspace hierarchy commit — workspace model, workspace routes, issue workspace_id FK, import commit workspace scoping. Findings as of 2026-06-22.
metadata:
  type: project
---

Workspace hierarchy commit audited 2026-06-22. Commit added Workspace model, workspace routes, nullable workspace_id FK on Issue, and workspace ownership check in POST /imports/commit.

**Why:** First real workspace/multi-tenancy infrastructure. Issues were previously per-user only.

**How to apply:** Use these findings as the baseline for all future workspace-scoped audits.

## Key findings

### SAFE items
- `GET /workspaces/{workspace_id}`: calls `get_workspace` (fetches by id only), then checks `ws.owner_id != current_user.id` → 404. Correct ownership enforcement and returns 404 not 403 (no enumeration).
- `POST /workspaces/`: forces `owner_id=current_user.id` in the service call — user cannot self-assign another owner.
- `workspace_service.get_workspace`: fetches by PK only. Authorization is caller's responsibility — correctly delegated to routes.
- `POST /imports/commit`: checks `ws.owner_id == current_user.id` before writing any issues. Guard is present and correct.
- All issue routes (`GET /board`, `POST /`, `PATCH /{id}`, `PATCH /{id}/move`, `DELETE /{id}`): all require `Depends(get_current_user)` and route through `_get_owned_issue` which filters by both `issue_id` AND `user_id`. Correct isolation.
- `issue_service.get_issue`: filters by both `Issue.id == issue_id` AND `Issue.user_id == user_id`. Safe.
- `issue_service.get_board`: filters by `Issue.user_id == user_id`. Safe for current architecture.
- `_ordered_column`: filters by `user_id` and `status`. No workspace leak path.

### FINDING — HIGH (CRITICAL): workspace_id accepted but NOT validated on POST /issues/
- `POST /issues/` route (`app/api/routes/issues.py` line 57-72) calls `issue_service.create_issue` but does NOT pass `workspace_id` at all — the schema `IssueCreate` does not include `workspace_id` field. Issues created via the board route are always workspace_id=NULL, which is fine for now. BUT if `IssueCreate` schema is ever extended to accept workspace_id, the route must validate ownership before passing it through.
- Risk: Not currently exploitable because the route doesn't accept workspace_id. Flag for migration.

### FINDING — HIGH (CRITICAL): workspace_id is nullable with no enforcement
- `Issue.workspace_id` is a nullable FK with `ondelete="SET NULL"`. This means if a workspace is deleted, all its issues silently become workspace_id=NULL and are absorbed into the no-workspace pool. No orphan detection. If `get_board` ever gains a workspace filter, these orphaned issues will be invisible.

### FINDING — MEDIUM: GET /board returns ALL user issues regardless of workspace_id
- `issue_service.get_board` filters only by `user_id`. If multi-workspace support is added (User A is a member of Workspace 1 and Workspace 2), this will mix issues from both workspaces in one board with no separation. Not exploitable now (only owner can be a member), but an architectural gap.

### FINDING — LOW: No test coverage for workspace ownership isolation
- No tests verify that User A cannot read User B's workspace via GET /workspaces/{id}.
- No tests verify that User A cannot import into User B's workspace via POST /imports/commit with workspace_id.
- The existing 20 import tests check per-user isolation for CSV rows but not workspace ownership enforcement.

### PENDING MIGRATION: All existing issue queries filter by user_id only
- `_ordered_column`, `get_board`, `get_issue`: all filter by user_id only. Will need workspace_id added when the board becomes workspace-scoped.
- `move_issue`, `delete_issue`: operate on pre-fetched Issue object (ownership checked at route layer), so no direct query risk.

## Architectural notes
- `workspace_service.get_workspace` is a bare fetch — intentionally. Authorization is always the caller's job. Pattern is consistent with how `issue_service.get_issue` works when called directly vs via the ownership helper.
- The `ondelete="SET NULL"` on `Issue.workspace_id` means workspace deletion does not cascade-delete issues. This is a business decision but creates orphan issues.
- No RLS policies exist — application-layer filtering is the only isolation mechanism.
