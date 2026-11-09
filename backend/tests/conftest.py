"""Shared L1/L2 fixtures (docs/03-test-plan.md §2): fresh_db, TestClient app.

Every test gets its own temporary SQLite file migrated to head via Alembic,
so the migration chain is exercised on every run (AC-C1 style, ITER-02: the
``users`` migration is the first real one).

The JWT secret is pinned per test so no dev key file is generated on test runs.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient

from alembic import command

BACKEND_ROOT = Path(__file__).resolve().parent.parent
TEST_JWT_SECRET = "test-only-secret-32-bytes-long-abcdef"
CSRF_HEADER = {"X-Requested-With": "investflow"}


def _alembic_upgrade_head(db_path: Path) -> None:
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    command.upgrade(cfg, "head")


def _app_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point INVESTFLOW_DB_PATH at a fresh per-test DB and migrate it."""
    db_path = tmp_path / "api-test.db"
    monkeypatch.setenv("INVESTFLOW_DB_PATH", str(db_path))
    monkeypatch.setenv("INVESTFLOW_JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.delenv("INVESTFLOW_COOKIE_SECURE", raising=False)
    monkeypatch.syspath_prepend(str(BACKEND_ROOT))
    os.chdir(BACKEND_ROOT)
    print(f"DEBUG_DB_PATH={db_path}")
    _alembic_upgrade_head(db_path)
    return db_path


def register(
    client: TestClient, username: str = "alice", password: str = "correct-horse-10"
) -> object:
    """Register a user through the API (auto-login per AC-U1a)."""
    return client.post(
        "/api/auth/register",
        headers=CSRF_HEADER,
        json={
            "username": username,
            "display_name": None,
            "password": password,
            "password_confirmation": password,
        },
    )


def login(
    client: TestClient, username: str = "alice", password: str = "correct-horse-10"
) -> object:
    return client.post(
        "/api/auth/login", headers=CSRF_HEADER, json={"username": username, "password": password}
    )


@pytest.fixture()
def app_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    return _app_env(tmp_path, monkeypatch)


@pytest.fixture()
def client(app_env: Path) -> Iterator[TestClient]:
    import importlib

    import app.main as app_main

    print(f"DEBUG_FIXTURE_DB={app_env}")
    importlib.reload(app_main)
    print(f"DEBUG_RELOADED_DB={app_main.resolve_db_path()}")
    app = app_main.create_app()
    print(f"DEBUG_APP_DB={app.state.db_path}")
    with TestClient(app) as c:
        yield c


def user_rows(db_path: Path, sql: str = "SELECT username, is_active FROM users") -> list[object]:
    import sqlite3

    conn = sqlite3.connect(db_path)
    try:
        rows = list(conn.execute(sql))  # type: ignore[arg-type]
        conn.commit()
        return rows
    finally:
        conn.close()
