from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from alembic.config import Config

from alembic import command
from app.crypto_store import (
    read_account_sensitive,
    rotate_account_sensitive_keys,
    write_account_sensitive,
)
from crypto.keyring import generate_key, get_active_key_id


def _upgrade_db(db_path: Path) -> None:
    backend_root = Path(__file__).resolve().parent.parent.parent
    cfg = Config(str(backend_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_root / "alembic"))
    command.upgrade(cfg, "head")


def test_account_sensitive_contract_stores_ciphertext_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "account_sensitive.db"
    keyring_path = tmp_path / "enc_keys.json"
    monkeypatch.setenv("INVESTFLOW_DB_PATH", str(db_path))
    monkeypatch.setenv("INVESTFLOW_ACTIVE_KEY_ID", "v1")
    monkeypatch.setenv("INVESTFLOW_ENC_KEYS", json.dumps({"v1": generate_key()}))
    monkeypatch.setenv("INVESTFLOW_ENC_KEY_FILE", str(keyring_path))

    _upgrade_db(db_path)
    account_number = "1234-5678-9012-3456"
    notes = "wire ref: 9876543210"
    write_account_sensitive(
        42,
        {
            "account_number_enc": account_number,
            "notes_enc": notes,
        },
    )

    raw_db = db_path.read_bytes()
    assert account_number.encode() not in raw_db
    assert notes.encode() not in raw_db

    row = (
        sqlite3.connect(db_path)
        .execute(
            "SELECT account_id, account_number_enc, notes_enc, key_id "
            "FROM account_sensitive WHERE account_id = 42"
        )
        .fetchone()
    )
    assert row is not None and row[3] == "v1"
    assert row[1] != account_number.encode()
    assert row[2] != notes.encode()

    loaded = read_account_sensitive(42)
    assert loaded["account_number_enc"] == account_number
    assert loaded["notes_enc"] == notes


def test_rotate_account_sensitive_keys_reencrypts_all_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "rotate_sensitive.db"
    keyring_path = tmp_path / "enc_keys.json"
    monkeypatch.setenv("INVESTFLOW_DB_PATH", str(db_path))
    monkeypatch.setenv("INVESTFLOW_ACTIVE_KEY_ID", "v1")
    monkeypatch.setenv("INVESTFLOW_ENC_KEYS", json.dumps({"v1": generate_key()}))
    monkeypatch.setenv("INVESTFLOW_ENC_KEY_FILE", str(keyring_path))
    _upgrade_db(db_path)

    original = {
        1: {"account_number_enc": "1111-2222-3333", "notes_enc": "alpha"},
        2: {"account_number_enc": "4444-5555-6666", "transfer_numbers_enc": "wire: 20"},
        3: {"routing_transit_enc": "67890", "notes_enc": "beta"},
    }
    for account_id, values in original.items():
        write_account_sensitive(account_id, values)

    count = rotate_account_sensitive_keys(
        "v2", db_path=str(db_path), keyring_path=str(keyring_path)
    )
    assert count == 3
    assert get_active_key_id() == "v2"

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT account_id, key_id FROM account_sensitive ORDER BY account_id"
        ).fetchall()
    assert [row[1] for row in rows] == ["v2", "v2", "v2"]
    for account_id, expected in original.items():
        loaded = read_account_sensitive(account_id)
        for field_name, value in expected.items():
            assert loaded[field_name] == value
