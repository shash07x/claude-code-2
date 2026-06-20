"""Tests for the Sprint Board (issues) API."""
from __future__ import annotations

import uuid

from app.core.config import settings

BASE = settings.API_V1_PREFIX + "/issues"
AUTH_BASE = settings.API_V1_PREFIX + "/auth"

COLUMNS = ["backlog", "review", "in_progress", "done"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _signup(client, email="user@example.com", password="Password123"):
    r = await client.post(
        f"{AUTH_BASE}/signup",
        json={"email": email, "password": password, "full_name": "Test User"},
    )
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _create(client, token, title, status="backlog", priority="medium"):
    r = await client.post(
        BASE,
        headers=_headers(token),
        json={"title": title, "status": status, "priority": priority},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _board(client, token) -> dict[str, list[dict]]:
    """Return {status: [items ordered by position]}."""
    r = await client.get(f"{BASE}/board", headers=_headers(token))
    assert r.status_code == 200, r.text
    return {col["status"]: col["items"] for col in r.json()["columns"]}


def _titles(items: list[dict]) -> list[str]:
    return [i["title"] for i in items]


def _positions(items: list[dict]) -> list[int]:
    return [i["position"] for i in items]


async def _move(client, token, issue_id, status, position):
    return await client.patch(
        f"{BASE}/{issue_id}/move",
        headers=_headers(token),
        json={"status": status, "position": position},
    )


# ---------------------------------------------------------------------------
# Board structure
# ---------------------------------------------------------------------------

async def test_board_requires_auth(client, db_session):
    r = await client.get(f"{BASE}/board")
    assert r.status_code == 401


async def test_board_has_four_columns_in_order(client, db_session):
    token = await _signup(client)
    r = await client.get(f"{BASE}/board", headers=_headers(token))
    assert r.status_code == 200
    cols = r.json()["columns"]
    assert [c["status"] for c in cols] == COLUMNS
    assert [c["title"] for c in cols] == ["Backlog", "Review", "In Progress", "Done"]
    assert all(c["items"] == [] for c in cols)


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

async def test_create_appends_to_backlog_by_default(client, db_session):
    token = await _signup(client)
    a = await _create(client, token, "A")
    b = await _create(client, token, "B")
    assert a["status"] == "backlog"
    assert a["position"] == 0
    assert b["position"] == 1

    board = await _board(client, token)
    assert _titles(board["backlog"]) == ["A", "B"]
    assert _positions(board["backlog"]) == [0, 1]


async def test_create_in_specific_column(client, db_session):
    token = await _signup(client)
    await _create(client, token, "R1", status="review")
    board = await _board(client, token)
    assert _titles(board["review"]) == ["R1"]
    assert _titles(board["backlog"]) == []


async def test_create_invalid_status_rejected(client, db_session):
    token = await _signup(client)
    r = await client.post(
        BASE, headers=_headers(token), json={"title": "X", "status": "nope"}
    )
    assert r.status_code == 422


async def test_create_requires_title(client, db_session):
    token = await _signup(client)
    r = await client.post(BASE, headers=_headers(token), json={"title": ""})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Move — within a column
# ---------------------------------------------------------------------------

async def test_move_within_column_to_top(client, db_session):
    token = await _signup(client)
    await _create(client, token, "A")
    await _create(client, token, "B")
    c = await _create(client, token, "C")

    r = await _move(client, token, c["id"], "backlog", 0)
    assert r.status_code == 200

    board = await _board(client, token)
    assert _titles(board["backlog"]) == ["C", "A", "B"]
    assert _positions(board["backlog"]) == [0, 1, 2]  # contiguous


async def test_move_within_column_to_middle(client, db_session):
    token = await _signup(client)
    a = await _create(client, token, "A")
    await _create(client, token, "B")
    await _create(client, token, "C")

    # Move A to index 1 (excluding-moved list is [B, C] → insert at 1 → B, A, C)
    r = await _move(client, token, a["id"], "backlog", 1)
    assert r.status_code == 200

    board = await _board(client, token)
    assert _titles(board["backlog"]) == ["B", "A", "C"]


# ---------------------------------------------------------------------------
# Move — across columns
# ---------------------------------------------------------------------------

async def test_move_across_columns_reindexes_both(client, db_session):
    token = await _signup(client)
    a = await _create(client, token, "A")
    b = await _create(client, token, "B")
    await _create(client, token, "C")

    # Move B → In Progress at index 0.
    r = await _move(client, token, b["id"], "in_progress", 0)
    assert r.status_code == 200
    moved = r.json()
    assert moved["status"] == "in_progress"
    assert moved["position"] == 0

    board = await _board(client, token)
    # Source column re-indexed contiguously.
    assert _titles(board["backlog"]) == ["A", "C"]
    assert _positions(board["backlog"]) == [0, 1]
    # Target column holds the moved card.
    assert _titles(board["in_progress"]) == ["B"]
    assert _positions(board["in_progress"]) == [0]


async def test_move_into_populated_column_at_index(client, db_session):
    token = await _signup(client)
    a = await _create(client, token, "A")
    await _create(client, token, "X", status="done")
    await _create(client, token, "Y", status="done")

    # Insert A between X and Y in Done (index 1).
    r = await _move(client, token, a["id"], "done", 1)
    assert r.status_code == 200

    board = await _board(client, token)
    assert _titles(board["done"]) == ["X", "A", "Y"]
    assert _positions(board["done"]) == [0, 1, 2]
    assert board["backlog"] == []


async def test_move_position_beyond_end_clamps_to_end(client, db_session):
    token = await _signup(client)
    await _create(client, token, "X", status="done")
    a = await _create(client, token, "A")

    r = await _move(client, token, a["id"], "done", 99)
    assert r.status_code == 200

    board = await _board(client, token)
    assert _titles(board["done"]) == ["X", "A"]


async def test_move_invalid_status_rejected(client, db_session):
    token = await _signup(client)
    a = await _create(client, token, "A")
    r = await _move(client, token, a["id"], "archived", 0)
    assert r.status_code == 422


async def test_move_negative_position_rejected(client, db_session):
    token = await _signup(client)
    a = await _create(client, token, "A")
    r = await _move(client, token, a["id"], "backlog", -1)
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Update + Delete
# ---------------------------------------------------------------------------

async def test_update_issue(client, db_session):
    token = await _signup(client)
    a = await _create(client, token, "A", priority="medium")
    r = await client.patch(
        f"{BASE}/{a['id']}",
        headers=_headers(token),
        json={"title": "A (edited)", "priority": "urgent"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "A (edited)"
    assert body["priority"] == "urgent"


async def test_delete_reindexes_column(client, db_session):
    token = await _signup(client)
    await _create(client, token, "A")
    b = await _create(client, token, "B")
    await _create(client, token, "C")

    r = await client.delete(f"{BASE}/{b['id']}", headers=_headers(token))
    assert r.status_code == 204

    board = await _board(client, token)
    assert _titles(board["backlog"]) == ["A", "C"]
    assert _positions(board["backlog"]) == [0, 1]  # gap closed


# ---------------------------------------------------------------------------
# Ownership isolation
# ---------------------------------------------------------------------------

async def test_board_only_shows_own_issues(client, db_session):
    token_a = await _signup(client, "a@example.com")
    token_b = await _signup(client, "b@example.com", password="Password456")
    await _create(client, token_a, "A-only")

    board_b = await _board(client, token_b)
    assert all(items == [] for items in board_b.values())


async def test_cannot_move_another_users_issue(client, db_session):
    token_a = await _signup(client, "a@example.com")
    token_b = await _signup(client, "b@example.com", password="Password456")
    a = await _create(client, token_a, "A")

    r = await _move(client, token_b, a["id"], "done", 0)
    assert r.status_code == 404


async def test_cannot_delete_another_users_issue(client, db_session):
    token_a = await _signup(client, "a@example.com")
    token_b = await _signup(client, "b@example.com", password="Password456")
    a = await _create(client, token_a, "A")

    r = await client.delete(f"{BASE}/{a['id']}", headers=_headers(token_b))
    assert r.status_code == 404


async def test_move_nonexistent_issue(client, db_session):
    token = await _signup(client)
    r = await _move(client, token, str(uuid.uuid4()), "done", 0)
    assert r.status_code == 404
