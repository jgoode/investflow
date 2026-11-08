from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from pathlib import Path

from crypto.keyring import (
    decode_key,
    generate_key,
    get_active_key_id,
    load_keyring,
    save_keyring,
    set_active_key_id,
)
from crypto.service import DecryptError, decrypt_field, encrypt_field, mask_secret

ACCOUNT_SENSITIVE_FIELDS = (
    "account_number_enc",
    "routing_transit_enc",
    "transfer_numbers_enc",
    "notes_enc",
)


def ensure_account_sensitive_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS settings ("
        "key TEXT PRIMARY KEY, "
        "value TEXT, "
        "value_type TEXT NOT NULL DEFAULT 'str', "
        "updated_at INTEGER NOT NULL DEFAULT 0)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS account_sensitive ("
        "account_id INTEGER PRIMARY KEY, "
        "account_number_enc BLOB, "
        "routing_transit_enc BLOB, "
        "transfer_numbers_enc BLOB, "
        "notes_enc BLOB, "
        "key_id TEXT NOT NULL DEFAULT 'v1')"
    )


def read_account_sensitive(
    account_id: int, *, conn: sqlite3.Connection | None = None
) -> dict[str, str | None]:
    local_conn = conn
    if local_conn is None:
        from app.db.connection import connect

        local_conn = connect()
        owned = True
    else:
        owned = False
    try:
        ensure_account_sensitive_db(local_conn)
        row = local_conn.execute(
            (
                "SELECT account_id, account_number_enc, routing_transit_enc, "
                "transfer_numbers_enc, notes_enc, key_id FROM account_sensitive "
                "WHERE account_id = ?"
            ),
            (account_id,),
        ).fetchone()
        if row is None:
            return {}
        keyring = load_keyring()
        out: dict[str, str | None] = {}
        for field in ACCOUNT_SENSITIVE_FIELDS:
            blob = row[field]
            key_id = row["key_id"]
            if blob is None:
                out[field] = None
                continue
            try:
                decoded = decrypt_field(
                    "account_sensitive",
                    field,
                    account_id,
                    blob,
                    key_id=key_id,
                    keyring=keyring,
                )
                out[field] = decoded
            except DecryptError:
                out[field] = None
        return out
    finally:
        if owned:
            local_conn.close()


def write_account_sensitive(
    account_id: int,
    values: Mapping[str, str | None],
    *,
    conn: sqlite3.Connection | None = None,
) -> dict[str, str | None]:
    local_conn = conn
    if local_conn is None:
        from app.db.connection import connect

        local_conn = connect()
        owned = True
    else:
        owned = False
    try:
        ensure_account_sensitive_db(local_conn)
        plaintext_values: dict[str, str | None] = {
            key: values.get(key) for key in ACCOUNT_SENSITIVE_FIELDS
        }
        encrypted_values: dict[str, bytes | None] = {}
        key_id = get_active_key_id()
        for field in ACCOUNT_SENSITIVE_FIELDS:
            plaintext = plaintext_values.get(field)
            if plaintext is None:
                continue
            encrypted_values[field] = encrypt_field(
                "account_sensitive", field, account_id, plaintext, key_id=key_id
            )
        local_conn.execute(
            (
                "INSERT INTO account_sensitive("
                "account_id, account_number_enc, routing_transit_enc, "
                "transfer_numbers_enc, notes_enc, key_id) VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(account_id) DO UPDATE SET "
                "account_number_enc = excluded.account_number_enc, "
                "routing_transit_enc = excluded.routing_transit_enc, "
                "transfer_numbers_enc = excluded.transfer_numbers_enc, "
                "notes_enc = excluded.notes_enc, "
                "key_id = excluded.key_id"
            ),
            (
                account_id,
                encrypted_values.get("account_number_enc"),
                encrypted_values.get("routing_transit_enc"),
                encrypted_values.get("transfer_numbers_enc"),
                encrypted_values.get("notes_enc"),
                key_id,
            ),
        )
        local_conn.commit()
        return read_account_sensitive(account_id, conn=local_conn)
    finally:
        if owned:
            local_conn.close()


def mask_account_sensitive(value: str | None, field_name: str) -> str:
    if value is None:
        return "•••"
    return mask_secret(value)


def rotate_account_sensitive_keys(
    new_key_id: str,
    *,
    db_path: str | Path | None = None,
    keyring_path: str | Path | None = None,
) -> int:
    from app.db.connection import connect

    keyring = load_keyring(keyring_path=keyring_path)
    if new_key_id not in keyring:
        keyring[new_key_id] = decode_key(generate_key())
        save_keyring(keyring, keyring_path)
    set_active_key_id(new_key_id, db_path=db_path)
    updated = 0
    with connect(db_path) as conn:
        ensure_account_sensitive_db(conn)
        rows = conn.execute(
            "SELECT account_id, account_number_enc, routing_transit_enc, "
            "transfer_numbers_enc, notes_enc, key_id FROM account_sensitive"
        ).fetchall()
        for row in rows:
            account_id = int(row["account_id"])
            new_values: dict[str, str | None] = {}
            for field in ACCOUNT_SENSITIVE_FIELDS:
                blob = row[field]
                if blob is None:
                    continue
                decrypted = decrypt_field(
                    "account_sensitive",
                    field,
                    account_id,
                    blob,
                    key_id=row["key_id"],
                    keyring=keyring,
                )
                new_values[field] = decrypted
            if not new_values:
                continue
            assignments: list[str] = []
            values: list[object] = []
            for field, plaintext in new_values.items():
                if plaintext is None:
                    continue
                assignments.append(f"{field} = ?")
                values.append(
                    encrypt_field(
                        "account_sensitive",
                        field,
                        account_id,
                        plaintext,
                        key_id=new_key_id,
                        keyring=keyring,
                    )
                )
            if not assignments:
                continue
            values.extend([new_key_id, account_id])
            conn.execute(
                (
                    f"UPDATE account_sensitive SET {', '.join(assignments)}, "
                    "key_id = ? WHERE account_id = ?"
                ),
                values,
            )
            updated += 1
        conn.commit()
    return updated
