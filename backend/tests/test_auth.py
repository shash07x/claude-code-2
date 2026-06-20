"""End-to-end tests for the auth flow (run against in-memory SQLite)."""
from __future__ import annotations

import re

from app.core.config import settings

BASE = settings.API_V1_PREFIX + "/auth"
COOKIE = settings.REFRESH_COOKIE_NAME

DEFAULT_EMAIL = "user@example.com"
DEFAULT_PASSWORD = "Password123"


async def signup(client, email=DEFAULT_EMAIL, password=DEFAULT_PASSWORD, name="Test User"):
    return await client.post(
        f"{BASE}/signup",
        json={"email": email, "password": password, "full_name": name},
    )


def cookie_value(client) -> str | None:
    for c in client.cookies.jar:
        if c.name == COOKIE:
            return c.value
    return None


# --- Signup ---

async def test_signup_success(client):
    r = await signup(client)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == DEFAULT_EMAIL
    assert body["user"]["is_active"] is True
    assert cookie_value(client) is not None  # refresh cookie set


async def test_signup_normalizes_email(client):
    r = await signup(client, email="MixedCase@Example.COM")
    assert r.status_code == 201
    assert r.json()["user"]["email"] == "mixedcase@example.com"


async def test_signup_duplicate_email(client):
    await signup(client)
    r = await signup(client)
    assert r.status_code == 409


async def test_signup_weak_password_rejected(client):
    r = await signup(client, password="short")
    assert r.status_code == 422  # fails Pydantic validation


# --- Login ---

async def test_login_success(client):
    await signup(client)
    client.cookies.clear()
    r = await client.post(
        f"{BASE}/login", json={"email": DEFAULT_EMAIL, "password": DEFAULT_PASSWORD}
    )
    assert r.status_code == 200, r.text
    assert r.json()["access_token"]
    assert cookie_value(client) is not None


async def test_login_wrong_password(client):
    await signup(client)
    r = await client.post(
        f"{BASE}/login", json={"email": DEFAULT_EMAIL, "password": "WrongPass123"}
    )
    assert r.status_code == 401


async def test_login_unknown_user(client):
    r = await client.post(
        f"{BASE}/login", json={"email": "nobody@example.com", "password": "Password123"}
    )
    assert r.status_code == 401


# --- Protected route ---

async def test_me_requires_authentication(client):
    r = await client.get(f"{BASE}/me")
    assert r.status_code == 401


async def test_me_with_valid_token(client):
    token = (await signup(client)).json()["access_token"]
    r = await client.get(f"{BASE}/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == DEFAULT_EMAIL


async def test_me_with_invalid_token(client):
    r = await client.get(
        f"{BASE}/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert r.status_code == 401


# --- Refresh + rotation ---

async def test_refresh_rotates_and_revokes_old(client):
    await signup(client)
    old = cookie_value(client)
    assert old

    r = await client.post(f"{BASE}/refresh")
    assert r.status_code == 200, r.text
    new = cookie_value(client)
    assert new and new != old  # token rotated

    # The old refresh token must now be revoked.
    client.cookies.clear()
    r2 = await client.post(f"{BASE}/refresh", headers={"Cookie": f"{COOKIE}={old}"})
    assert r2.status_code == 401


async def test_refresh_without_cookie(client):
    r = await client.post(f"{BASE}/refresh")
    assert r.status_code == 401


# --- Logout ---

async def test_logout_revokes_session(client):
    await signup(client)
    old = cookie_value(client)

    r = await client.post(f"{BASE}/logout")
    assert r.status_code == 204

    client.cookies.clear()
    r2 = await client.post(f"{BASE}/refresh", headers={"Cookie": f"{COOKIE}={old}"})
    assert r2.status_code == 401


# --- Password reset ---

async def test_password_reset_full_flow(client, email_recorder):
    await signup(client)

    # 1. Request a reset.
    r = await client.post(f"{BASE}/password-reset/request", json={"email": DEFAULT_EMAIL})
    assert r.status_code == 202
    assert len(email_recorder.messages) == 1

    # 2. Extract the token from the emailed link.
    body = email_recorder.messages[-1].body
    match = re.search(r"token=([A-Za-z0-9_\-]+)", body)
    assert match, body
    token = match.group(1)

    # 3. Confirm with a new password.
    new_password = "NewPassword456"
    r = await client.post(
        f"{BASE}/password-reset/confirm",
        json={"token": token, "new_password": new_password},
    )
    assert r.status_code == 200, r.text

    # 4. Old password no longer works; new one does.
    client.cookies.clear()
    r_old = await client.post(
        f"{BASE}/login", json={"email": DEFAULT_EMAIL, "password": DEFAULT_PASSWORD}
    )
    assert r_old.status_code == 401
    r_new = await client.post(
        f"{BASE}/login", json={"email": DEFAULT_EMAIL, "password": new_password}
    )
    assert r_new.status_code == 200


async def test_password_reset_unknown_email_is_silent(client, email_recorder):
    r = await client.post(
        f"{BASE}/password-reset/request", json={"email": "ghost@example.com"}
    )
    assert r.status_code == 202  # same response as a known email
    assert len(email_recorder.messages) == 0  # but nothing actually sent


async def test_password_reset_invalid_token(client):
    r = await client.post(
        f"{BASE}/password-reset/confirm",
        json={"token": "totally-invalid", "new_password": "NewPassword456"},
    )
    assert r.status_code == 400


async def test_password_reset_token_single_use(client, email_recorder):
    await signup(client)
    await client.post(f"{BASE}/password-reset/request", json={"email": DEFAULT_EMAIL})
    token = re.search(
        r"token=([A-Za-z0-9_\-]+)", email_recorder.messages[-1].body
    ).group(1)

    first = await client.post(
        f"{BASE}/password-reset/confirm",
        json={"token": token, "new_password": "NewPassword456"},
    )
    assert first.status_code == 200
    # Reusing the same token must fail.
    second = await client.post(
        f"{BASE}/password-reset/confirm",
        json={"token": token, "new_password": "AnotherPass789"},
    )
    assert second.status_code == 400
