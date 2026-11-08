"""SQLite connection layer (docs/02-architecture.md §3, §7).

Conventions:
    - WAL journal mode
    - ``PRAGMA foreign_keys=ON``
    - ``busy_timeout = 5000`` (§7 port-matrix note)
    - DB location configurable via the ``INVESTFLOW_DB_PATH`` env var (§7 Env vars)

The three pragmas live in ``apply_pragmas`` so the SQLAlchemy engine (later
iterations) and ``alembic/env.py`` can reuse exactly the same behavior.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Final

ENV_DB_PATH: Final[str] = "INVESTFLOW_DB_PATH"
BUSY_TIMEOUT_MS: Final[int] = 5000

# backend/data/investflow.db relative to this file (backend/app/db/connection.py).
_DEFAULT_DB_PATH: Final[Path] = (
    Path(__file__).resolve().parent.parent.parent / "data" / "investflow.db"
)


def default_db_path() -> Path:
    return _DEFAULT_DB_PATH


def resolve_db_path() -> Path:
    configured = os.environ.get(ENV_DB_PATH, "").strip()
    return Path(configured) if configured else _DEFAULT_DB_PATH


def apply_pragmas(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")


def connect(path: Path | None = None) -> sqlite3.Connection:
    db_path = path if path is not None else resolve_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    apply_pragmas(conn)
    return conn
