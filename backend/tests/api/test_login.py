"""L2 API tests — POST /api/auth/login (FR-U2 / ITER-02).

AC-U2a success → cookie,
AC-U2b inactive user → generic failure (no account-state leak),
AC-U2c generic + timing-equal failure, 5-failure throttle with pinned clock.
AC-U2d (authenticated visitor to /login redirects to dashboard) is frontend
behavior — covered at L4 and L3.
"""

from __future__ import annotations

import time

import time_machine
from fastapi.testclient import TestClient

from tests.conftest import login, register, user_rows

GENERIC_FAILURE = "invalid username or password"


def test_login_success_sets_cookie(client: TestClient) -> None:
    """AC-U2a: correct credentials → 200 + investflow_session cookie."""
    register(client, "alice")

    resp = login(client, "alice")

    assert resp.status_code == 200
    assert "investflow_session=" in resp.headers["set-cookie"]
    assert resp.json()["user"]["username"] == "alice"
    assert "password" not in resp.json()["user"]
    assert "password_hash" not in resp.json()["user"]


def test_login_wrong_password_generic_failure(client: TestClient) -> None:
    """AC-U2c: wrong password → 401, same generic message, no detail leakage."""
    register(client, "alice")

    resp = login(client, "alice", "wrong-pass-999")

    assert resp.status_code == 401
    assert resp.json()["detail"] == GENERIC_FAILURE


def test_login_unknown_user_same_generic_failure(client: TestClient) -> None:
    """AC-U2c: unknown username → identical generic message as wrong password."""
    register(client, "alice")  # irrelevant to the unknown-user attempt

    resp = login(client, "nobody", "long-enough-pass")

    assert resp.status_code == 401
    assert resp.json()["detail"] == GENERIC_FAILURE


def test_login_inactive_user_generic_failure(client: TestClient) -> None:
    """AC-U2b: inactive account with CORRECT credentials → generic failure.
    The message must not reveal the account state."""
    db = client.app.state.db_path  # type: ignore[attr-defined]
    register(client, "ghost")
    uid = user_rows(db, "SELECT id FROM users")[0][0]
    user_rows(db, f"UPDATE users SET is_active = 0 WHERE id = {uid}")

    resp = login(client, "ghost", "correct-horse-10")

    assert resp.status_code == 401
    body = resp.json()["detail"]
    assert body == GENERIC_FAILURE
    assert "inactiv" not in body.lower()


def test_login_failure_timing_equal(client: TestClient) -> None:
    """AC-U2c / docs/03-test-plan.md §5.1: unknown-user path must take the same
    deliberately slowed comparison as valid-user+wrong-password. Ratio asserted
    within a 2× fudge factor (argon2 verify dominates both paths)."""
    register(client, "alice")
    known_wrong_pw: list[float] = []
    unknown_user: list[float] = []
    # Distinguishable-by-both-sources heuristic does not exist; throttle window
    # must stay open, else argon2 would be skipped on throttle-check — we use
    # distinct usernames so the failure counter never trips mid-measurement.

    with time_machine.travel("2026-11-08 12:00:00 +00:00", tick=False):
        for i in range(5):
            start = time.perf_counter()
            login(client, "alice", f"wrong-pass-{i}")
            known_wrong_pw.append(time.perf_counter() - start)

            start = time.perf_counter()
            login(client, f"nobody{i}", f"wrong-pass-{i}")
            unknown_user.append(time.perf_counter() - start)

    known_median = sorted(known_wrong_pw)[2]
    unknown_median = sorted(unknown_user)[2]
    slowest, fastest = max(known_median, unknown_median), min(known_median, unknown_median)
    assert slowest / fastest < 2.0, (
        f"timing divergence: known={known_median:.3f}s unknown={unknown_median:.3f}s"
    )


def test_login_throttle_blocks_sixth_attempt_even_with_correct_password(
    client: TestClient,
) -> None:
    """AC-U2c: after 5 consecutive failures the account is throttled — even
    correct credentials are refused while the throttle window is open."""
    register(client, "alice")
    for i in range(5):
        assert login(client, "alice", f"wrong-pass-{i}").status_code == 401

    resp = login(client, "alice", "correct-horse-10")

    assert resp.status_code == 429


def test_login_throttle_lifts_after_fifteen_minutes(client: TestClient) -> None:
    """AC-U2c: throttle lasts 15 minutes — proven by shifting the pinned clock
    (time-machine), never by sleeping."""
    register(client, "alice")
    with time_machine.travel("2026-11-08 12:00:00 +00:00", tick=False) as traveller:
        for i in range(5):
            login(client, "alice", f"wrong-pass-{i}")
        assert login(client, "alice", "correct-horse-10").status_code == 429

        traveller.shift(15 * 60 + 1)

        assert login(client, "alice", "correct-horse-10").status_code == 200


def test_login_success_resets_failure_counter(client: TestClient) -> None:
    """AC-U2c: 'consecutive failures' — a success clears the counter:
    4 failures + a success + 4 more failures must NOT behave as ≥5 consecutive."""
    register(client, "alice")
    with time_machine.travel("2026-11-08 12:00:00 +00:00", tick=False) as traveller:
        for i in range(4):
            assert login(client, "alice", f"wrong-pass-{i}").status_code == 401

        traveller.shift(60)  # inside throttle window, but failures will be cleared
        assert login(client, "alice", "correct-horse-10").status_code == 200

        for i in range(4):
            assert login(client, "alice", f"wrong-pass-{i}").status_code == 401
        assert login(client, "alice", f"wrong-pass-{i}").status_code == 401


def test_login_throttle_uniform_for_unknown_users(client: TestClient) -> None:
    """ITER-02 decision (user-approved): throttle is uniform for any submitted
    username, including nonexistent ones (enumeration resistance — 03 §5.4)."""
    for i in range(5):
        assert login(client, "phantom", f"wrong-pass-{i}").status_code == 401

    resp = login(client, "phantom", "long-enough-pass")

    assert resp.status_code == 429


def test_login_does_not_leak_password_in_error_response(client: TestClient) -> None:
    """NFR-3: error bodies never echo credentials."""
    register(client, "alice")

    resp = login(client, "alice", "wrong-pass-999")

    body_text = resp.text
    assert "wrong-pass-999" not in body_text
