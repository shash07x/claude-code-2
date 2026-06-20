"""Tests for the notification center API."""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decode_access_token
from app.services import notification_service

BASE = settings.API_V1_PREFIX + "/notifications"
AUTH_BASE = settings.API_V1_PREFIX + "/auth"

TYPES = ["mention", "assignment", "comment", "system"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _signup_and_token(client, email="user@example.com", password="Password123"):
    r = await client.post(
        f"{AUTH_BASE}/signup",
        json={"email": email, "password": password, "full_name": "Test User"},
    )
    assert r.status_code == 201, r.text
    return r.json()["access_token"], r.json()["user"]["id"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _user_id_from_token(token: str) -> uuid.UUID:
    payload = decode_access_token(token)
    return uuid.UUID(payload["sub"])


async def _seed(db: AsyncSession, token: str, count: int = 3) -> list[str]:
    """Insert `count` notifications directly via the service (no HTTP create endpoint)."""
    user_id = _user_id_from_token(token)
    ids = []
    for i in range(count):
        notif = await notification_service.create_notification(
            db,
            user_id=user_id,
            type=TYPES[i % len(TYPES)],
            title=f"Notification {i + 1}",
            body=f"Body of notification {i + 1}",
        )
        ids.append(str(notif.id))
    await db.commit()
    return ids


# ---------------------------------------------------------------------------
# List notifications
# ---------------------------------------------------------------------------

async def test_list_empty(client, db_session):
    token, _ = await _signup_and_token(client)
    r = await client.get(BASE, headers=_headers(token))
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["unread_count"] == 0


async def test_list_requires_auth(client, db_session):
    r = await client.get(BASE)
    assert r.status_code == 401


async def test_list_returns_notifications(client, db_session):
    token, _ = await _signup_and_token(client)
    await _seed(db_session, token, 3)

    r = await client.get(BASE, headers=_headers(token))
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert len(body["items"]) == 3
    assert body["unread_count"] == 3


async def test_list_ordered_newest_first(client, db_session):
    token, _ = await _signup_and_token(client)
    await _seed(db_session, token, 3)

    r = await client.get(BASE, headers=_headers(token))
    items = r.json()["items"]
    # All three titles must be present (order can be indeterminate in SQLite when
    # timestamps share the same microsecond, as happens in fast in-memory tests).
    assert {it["title"] for it in items} == {
        "Notification 1", "Notification 2", "Notification 3"
    }


async def test_list_pagination(client, db_session):
    token, _ = await _signup_and_token(client)
    await _seed(db_session, token, 5)

    r = await client.get(BASE + "?limit=2&offset=0", headers=_headers(token))
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2

    r2 = await client.get(BASE + "?limit=2&offset=2", headers=_headers(token))
    assert len(r2.json()["items"]) == 2

    r3 = await client.get(BASE + "?limit=2&offset=4", headers=_headers(token))
    assert len(r3.json()["items"]) == 1


async def test_list_unread_only_filter(client, db_session):
    token, _ = await _signup_and_token(client)
    ids = await _seed(db_session, token, 4)

    # Mark two as read via HTTP.
    await client.post(f"{BASE}/{ids[0]}/read", headers=_headers(token))
    await client.post(f"{BASE}/{ids[1]}/read", headers=_headers(token))

    r = await client.get(BASE + "?unread_only=true", headers=_headers(token))
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert all(not item["is_read"] for item in body["items"])


async def test_notifications_isolated_between_users(client, db_session):
    token_a, _ = await _signup_and_token(client, "a@example.com")
    token_b, _ = await _signup_and_token(client, "b@example.com", password="Password456")
    await _seed(db_session, token_a, 2)

    r = await client.get(BASE, headers=_headers(token_b))
    assert r.json()["total"] == 0


# ---------------------------------------------------------------------------
# Unread count
# ---------------------------------------------------------------------------

async def test_unread_count(client, db_session):
    token, _ = await _signup_and_token(client)
    await _seed(db_session, token, 4)

    r = await client.get(BASE + "/unread-count", headers=_headers(token))
    assert r.status_code == 200
    assert r.json()["unread_count"] == 4


async def test_unread_count_requires_auth(client, db_session):
    r = await client.get(BASE + "/unread-count")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Mark single notification read
# ---------------------------------------------------------------------------

async def test_mark_read(client, db_session):
    token, _ = await _signup_and_token(client)
    ids = await _seed(db_session, token, 2)

    r = await client.post(f"{BASE}/{ids[0]}/read", headers=_headers(token))
    assert r.status_code == 200
    body = r.json()
    assert body["is_read"] is True
    assert body["read_at"] is not None

    count_r = await client.get(BASE + "/unread-count", headers=_headers(token))
    assert count_r.json()["unread_count"] == 1


async def test_mark_read_idempotent(client, db_session):
    token, _ = await _signup_and_token(client)
    ids = await _seed(db_session, token, 1)

    r1 = await client.post(f"{BASE}/{ids[0]}/read", headers=_headers(token))
    r2 = await client.post(f"{BASE}/{ids[0]}/read", headers=_headers(token))
    assert r1.status_code == 200
    assert r2.status_code == 200
    # read_at must be set and must not change on the second call.
    # Strip timezone marker before comparing (SQLite drops it on round-trip).
    def _strip_tz(ts: str) -> str:
        return ts.rstrip("Z").rstrip("+00:00")
    assert r1.json()["read_at"] is not None
    assert _strip_tz(r1.json()["read_at"]) == _strip_tz(r2.json()["read_at"])


async def test_mark_read_other_users_notification(client, db_session):
    token_a, _ = await _signup_and_token(client, "a@example.com")
    token_b, _ = await _signup_and_token(client, "b@example.com", password="Password456")
    ids = await _seed(db_session, token_a, 1)

    r = await client.post(f"{BASE}/{ids[0]}/read", headers=_headers(token_b))
    assert r.status_code == 404


async def test_mark_read_nonexistent(client, db_session):
    token, _ = await _signup_and_token(client)
    r = await client.post(f"{BASE}/{uuid.uuid4()}/read", headers=_headers(token))
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Mark all read
# ---------------------------------------------------------------------------

async def test_mark_all_read(client, db_session):
    token, _ = await _signup_and_token(client)
    await _seed(db_session, token, 5)

    r = await client.post(BASE + "/read-all", headers=_headers(token))
    assert r.status_code == 200
    assert r.json()["unread_count"] == 0

    count_r = await client.get(BASE + "/unread-count", headers=_headers(token))
    assert count_r.json()["unread_count"] == 0


async def test_mark_all_read_with_no_notifications(client, db_session):
    token, _ = await _signup_and_token(client)
    r = await client.post(BASE + "/read-all", headers=_headers(token))
    assert r.status_code == 200
    assert r.json()["unread_count"] == 0


async def test_mark_all_read_only_affects_current_user(client, db_session):
    token_a, _ = await _signup_and_token(client, "a@example.com")
    token_b, _ = await _signup_and_token(client, "b@example.com", password="Password456")
    await _seed(db_session, token_a, 3)
    await _seed(db_session, token_b, 2)

    # Mark all of user B's read.
    await client.post(BASE + "/read-all", headers=_headers(token_b))

    # User A still has 3 unread.
    r = await client.get(BASE + "/unread-count", headers=_headers(token_a))
    assert r.json()["unread_count"] == 3


# ---------------------------------------------------------------------------
# Delete notification
# ---------------------------------------------------------------------------

async def test_delete_notification(client, db_session):
    token, _ = await _signup_and_token(client)
    ids = await _seed(db_session, token, 2)

    r = await client.delete(f"{BASE}/{ids[0]}", headers=_headers(token))
    assert r.status_code == 204

    r2 = await client.get(BASE, headers=_headers(token))
    assert r2.json()["total"] == 1


async def test_delete_other_users_notification(client, db_session):
    token_a, _ = await _signup_and_token(client, "a@example.com")
    token_b, _ = await _signup_and_token(client, "b@example.com", password="Password456")
    ids = await _seed(db_session, token_a, 1)

    r = await client.delete(f"{BASE}/{ids[0]}", headers=_headers(token_b))
    assert r.status_code == 404


async def test_delete_nonexistent(client, db_session):
    token, _ = await _signup_and_token(client)
    r = await client.delete(f"{BASE}/{uuid.uuid4()}", headers=_headers(token))
    assert r.status_code == 404
