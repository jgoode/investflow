"""L1 unit tests — SQLite connection layer conventions.

Conventions under test (docs/02-architecture.md §3 + §7):
    - WAL journal mode
    - PRAGMA foreign_keys=ON
    - busy_timeout = 5000 ms (port-matrix note, §7)
    - DB location configurable via INVESTFLOW_DB_PATH env var
"""

import sqlite3
from pathlib import Path

from app.db.connection import (
    BUSY_TIMEOUT_MS,
    connect,
    default_db_path,
    resolve_db_path,
)


def test_connect_returns_sqlite3_connection(tmp_path: Path) -> None:
    conn = connect(tmp_path / "fresh.db")

    assert isinstance(conn, sqlite3.Connection)


def test_connect_enables_wal_journal_mode(tmp_path: Path) -> None:
    conn = connect(tmp_path / "fresh.db")

    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_connect_enables_foreign_keys(tmp_path: Path) -> None:
    conn = connect(tmp_path / "fresh.db")

    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_connect_sets_busy_timeout_per_architecture_doc(tmp_path: Path) -> None:
    conn = connect(tmp_path / "fresh.db")

    assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == BUSY_TIMEOUT_MS
    assert BUSY_TIMEOUT_MS == 5000


def test_default_db_path_is_repo_data_file() -> None:
    """Default layout: backend/data/investflow.db (02 §7 INVESTFLOW_DB_PATH / dev default)."""
    assert default_db_path().name == "investflow.db"


def test_resolve_db_path_reads_env_var(tmp_path: Path, monkeypatch: "object") -> None:

    env_path = tmp_path / "custom" / "alt.db"
    monkeypatch.setenv("INVESTFLOW_DB_PATH", str(env_path))

    assert resolve_db_path() == env_path


def test_connect_creates_parent_directories(tmp_path: Path) -> None:
    db_file = tmp_path / "nested" / "dir" / "insert.db"

    conn = connect(db_file)

    assert db_file.exists()
    conn.close()
