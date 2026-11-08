from __future__ import annotations

import base64
import json
import os
import secrets
import sqlite3
from collections.abc import Mapping
from pathlib import Path
from typing import Any

KEYRING_ENV = "INVESTFLOW_ENC_KEYS"
KEYRING_FILE_ENV = "INVESTFLOW_ENC_KEY_FILE"
LEGACY_KEY_ENV = "INVESTFLOW_ENC_KEY"
ACTIVE_KEY_ENV = "INVESTFLOW_ACTIVE_KEY_ID"


def generate_key() -> str:
    return encode_key(secrets.token_bytes(32))


def encode_key(secret: bytes) -> str:
    return base64.b64encode(secret).decode("ascii")


def decode_key(value: str) -> bytes:
    return base64.b64decode(value.encode("ascii"))


def default_key_file() -> Path:
    return Path.home() / ".investflow" / "enc_keys.json"


def _current_key_file() -> Path:
    configured = os.environ.get(KEYRING_FILE_ENV, "").strip()
    if configured:
        return Path(configured)
    return default_key_file()


def _canonicalize_keyring(raw_keyring: Mapping[str, Any]) -> dict[str, bytes]:
    normalized: dict[str, bytes] = {}
    for key_id, encoded in raw_keyring.items():
        if isinstance(encoded, (bytes, bytearray)):
            normalized[str(key_id)] = bytes(encoded)
        else:
            normalized[str(key_id)] = decode_key(str(encoded))
    return dict(sorted(normalized.items()))


def load_keyring(
    *, keyring_path: str | Path | None = None, env: Mapping[str, str] | None = None
) -> dict[str, bytes]:
    if env is None:
        env = os.environ

    configured = str(env.get(KEYRING_ENV, "")).strip()
    if configured:
        raw = json.loads(configured)
        keyring = _canonicalize_keyring(raw)
        if keyring_path is not None:
            save_keyring(keyring, keyring_path)
        return keyring

    legacy = str(env.get(LEGACY_KEY_ENV, "")).strip()
    if legacy:
        key_id = str(env.get(ACTIVE_KEY_ENV, "v1")).strip() or "v1"
        keyring = {key_id: legacy}
        if keyring_path is not None:
            save_keyring(keyring, keyring_path)
        return _canonicalize_keyring(keyring)

    path = Path(keyring_path) if keyring_path is not None else _current_key_file()
    if path.exists():
        file_contents = json.loads(path.read_text(encoding="utf-8"))
        return _canonicalize_keyring(file_contents)

    default_key = {"v1": generate_key()}
    save_keyring(default_key, path)
    return _canonicalize_keyring(default_key)


def save_keyring(keyring: Mapping[str, bytes | str], path: str | Path | None = None) -> Path:
    target_path = Path(path) if path is not None else _current_key_file()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {}
    for key_id, value in sorted(keyring.items()):
        if isinstance(value, (bytes, bytearray)):
            payload[str(key_id)] = encode_key(bytes(value))
        else:
            payload[str(key_id)] = str(value)
    target_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    os.chmod(target_path, 0o600)
    return target_path


def get_active_key_id(*, db_path: str | Path | None = None) -> str:
    configured = os.environ.get(ACTIVE_KEY_ENV, "").strip()
    if configured:
        return configured

    if db_path is None:
        db_path = os.environ.get("INVESTFLOW_DB_PATH", "")
    if db_path:
        try:
            with sqlite3.connect(db_path) as conn:
                row = conn.execute(
                    "SELECT value FROM settings WHERE key = 'active_key_id' LIMIT 1"
                ).fetchone()
                if row is not None and row[0]:
                    return str(row[0])
        except sqlite3.DatabaseError:
            pass

    keyring = load_keyring()
    if not keyring:
        raise RuntimeError("No encryption keys are configured.")
    return next(iter(sorted(keyring)))


def set_active_key_id(key_id: str, *, db_path: str | Path | None = None) -> str:
    os.environ[ACTIVE_KEY_ENV] = key_id
    if db_path is None:
        db_path = os.environ.get("INVESTFLOW_DB_PATH", "")
    if db_path:
        try:
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS settings ("
                    "key TEXT PRIMARY KEY, "
                    "value TEXT, "
                    "value_type TEXT DEFAULT 'str', "
                    "updated_at INTEGER DEFAULT 0)"
                )
                conn.execute(
                    "INSERT INTO settings(key, value, value_type, updated_at) "
                    "VALUES (?, ?, 'str', CAST(strftime('%s','now') AS INTEGER)) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
                    "updated_at = excluded.updated_at",
                    ("active_key_id", key_id),
                )
                conn.commit()
        except sqlite3.DatabaseError:
            pass
    return key_id


def rotate_keyring(
    new_key_id: str,
    *,
    old_key_id: str | None = None,
    keyring_path: str | Path | None = None,
    db_path: str | Path | None = None,
) -> str:
    keyring = load_keyring(keyring_path=keyring_path)
    if new_key_id not in keyring:
        keyring[new_key_id] = generate_key()
    if old_key_id is not None and old_key_id not in keyring:
        keyring[old_key_id] = generate_key()
    save_keyring(keyring, keyring_path)
    set_active_key_id(new_key_id, db_path=db_path)
    return new_key_id


from crypto.service import decrypt_field, encrypt_field, mask_secret  # noqa: E402,F401
