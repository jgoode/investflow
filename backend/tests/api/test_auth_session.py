"""L2 API tests — auth session/guard behaviors (FR-U3, NFR-2, NFR-3)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from tests.conftest import CSRF_HEADER, register, user_rows


def test_api_guard_matrix_requires_auth_for_non_exempt_paths(client: TestClient) -> None:
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/logout", headers=CSRF_HEADER).status_code == 401
    assert client.get("/api/unknown").status_code == 401
    assert client.get("/api/healthz").status_code == 200


def test_csrf_header_required_for_mutating_auth_routes(client: TestClient) -> None:
    resp = client.post(
        "/api/auth/login",
        json={"username": "anybody", "password": "long-enough-pass"},
    )
    assert resp.status_code == 403


def test_me_returns_authenticated_user(client: TestClient) -> None:
    register(client, "alice")
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["username"] == "alice"


def test_logout_clears_session_cookie_and_subsequent_me_is_401(client: TestClient) -> None:
    register(client, "alice")
    logout = client.post("/api/auth/logout", headers=CSRF_HEADER)

    assert logout.status_code == 200
    set_cookie = logout.headers["set-cookie"].lower()
    assert "investflow_session=" in set_cookie
    assert "max-age=0" in set_cookie or "expires=" in set_cookie
    assert client.get("/api/auth/me").status_code == 401


def test_session_cookie_flags_are_httponly_and_samesite_lax(client: TestClient) -> None:
    resp = register(client, "alice")
    set_cookie = resp.headers["set-cookie"].lower()
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie


def test_session_epoch_revocation_invalidates_existing_cookie(client: TestClient) -> None:
    register(client, "alice")
    db = client.app.state.db_path  # type: ignore[attr-defined]
    user_rows(db, "UPDATE users SET session_epoch = session_epoch + 1 WHERE username = 'alice'")

    assert client.get("/api/auth/me").status_code == 401


def test_login_cookie_secure_flag_enabled_when_env_switch_is_on(
    tmp_path,
    monkeypatch,
) -> None:
    from alembic.config import Config

    from alembic import command
    from app.main import create_app

    backend_root = Path(__file__).resolve().parent.parent.parent
    db_path = tmp_path / "secure-cookie.db"
    monkeypatch.setenv("INVESTFLOW_DB_PATH", str(db_path))
    monkeypatch.setenv("INVESTFLOW_JWT_SECRET", "test-only-secret-32-bytes-long-abcdef")
    monkeypatch.setenv("INVESTFLOW_COOKIE_SECURE", "true")

    cfg = Config(str(backend_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_root / "alembic"))
    command.upgrade(cfg, "head")

    with TestClient(create_app()) as secure_client:
        resp = register(secure_client, "securealice")
    assert "secure" in resp.headers["set-cookie"].lower()
