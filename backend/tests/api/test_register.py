"""L2 API tests — POST /api/auth/register (FR-U1 / ITER-02).

AC-U1a valid registration (+ auto-login),
AC-U1b duplicate username,
AC-U1c validation mirrored server-side (422),
AC-U1d registration rate limit (≥5 in 10 min → 429, pinned clock — no real sleeps).
"""

from __future__ import annotations

import time_machine
from fastapi.testclient import TestClient

from tests.conftest import CSRF_HEADER, register, user_rows


def test_register_success_creates_user_and_logs_in(client: TestClient) -> None:
    """AC-U1a: user written (argon2id), session cookie set, /me echoes the user."""
    resp = register(client, "alice")

    assert resp.status_code == 200
    set_cookie = resp.headers["set-cookie"]
    assert "investflow_session=" in set_cookie

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["username"] == "alice"


def test_register_hash_is_argon2id_not_plaintext(client: TestClient) -> None:
    """AC-U1a/NFR-3: stored password is an argon2id hash, never plaintext
    (hash format itself is unit-tested in tests/unit/test_passwords.py)."""
    register(client, "hashcheck")

    rows = user_rows(client.app.state.db_path)  # type: ignore[attr-defined]
    assert rows == [("hashcheck", 1)]


def test_register_duplicate_username(client: TestClient) -> None:
    """AC-U1b: duplicate is refused inline; no second user written."""
    assert register(client, "alice").status_code == 200

    dup = register(client, "alice", "different-pass-99")
    assert dup.status_code == 409
    assert "already taken" in dup.json()["detail"]

    rows = user_rows(client.app.state.db_path)  # type: ignore[attr-defined]
    assert len(rows) == 1


def test_register_rejects_short_password_as_422(client: TestClient) -> None:
    """AC-U1c: password < 10 chars → 422 (mirrors client-side validation)."""
    resp = client.post(
        "/api/auth/register",
        headers=CSRF_HEADER,
        json={
            "username": "shorty",
            "display_name": None,
            "password": "ab1",
            "password_confirmation": "ab1",
        },
    )
    assert resp.status_code == 422


def test_register_rejects_uppercased_username(client: TestClient) -> None:
    """AC-U1c: uppercase (and spaces) in username violate ^[a-z0-9._-]+$ → 422."""
    for bad in ("Alice", "al ice", "al!ce"):
        resp = client.post(
            "/api/auth/register",
            headers=CSRF_HEADER,
            json={
                "username": bad,
                "display_name": None,
                "password": "long-enough-pass",
                "password_confirmation": "long-enough-pass",
            },
        )
        assert resp.status_code == 422, f"username={bad!r}"


def test_register_rejects_mismatched_confirmation(client: TestClient) -> None:
    """AC-U1c: confirmation mismatch → 422 before any state mutation."""
    resp = client.post(
        "/api/auth/register",
        headers=CSRF_HEADER,
        json={
            "username": "mismatch",
            "display_name": None,
            "password": "long-enough-pass",
            "password_confirmation": "long-enough-diff",
        },
    )
    assert resp.status_code == 422
    rows = user_rows(client.app.state.db_path)  # type: ignore[attr-defined]
    assert rows == []


def test_register_rejects_password_equal_to_username(client: TestClient) -> None:
    """FR-U1: password must not equal username."""
    resp = client.post(
        "/api/auth/register",
        headers=CSRF_HEADER,
        json={
            "username": "same.as.pw",
            "display_name": None,
            "password": "same.as.pw-x",
            "password_confirmation": "same.as.pw-x",
        },
    )
    assert resp.status_code == 422


def test_register_rate_limit_fifth_attempt_refused(client: TestClient) -> None:
    """AC-U1d: ≥5 registrations complete → further attempts 429 for 10 min window."""
    for i in range(5):
        resp = register(client, f"user{i}")
        assert resp.status_code == 200, f"registration {i} should succeed"

    sixth = register(client, "user5")
    assert sixth.status_code == 429


def test_register_rate_limit_reopens_after_window(client: TestClient) -> None:
    """AC-U1d: the window is 10 minutes; a pinned clock (never real sleeps)
    proves the 429 unlocks right after it passes."""
    with time_machine.travel("2026-11-08 12:00:00 +00:00", tick=False) as traveller:
        for i in range(5):
            register(client, f"user{i}")
        assert register(client, "user5").status_code == 429

        traveller.shift(10 * 60 + 1)

        resp = register(client, "user6", "after-window-pass")
        assert resp.status_code == 200
