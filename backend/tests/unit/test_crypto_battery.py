from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from crypto.keyring import (
    KEYRING_ENV,
    decrypt_field,
    encrypt_field,
    generate_key,
    get_active_key_id,
    load_keyring,
    mask_secret,
    rotate_keyring,
    save_keyring,
)
from crypto.service import DecryptError


@pytest.fixture()
def keyring_file(tmp_path: Path) -> Path:
    key_path = tmp_path / "enc_keys.json"
    save_keyring({"v1": generate_key()}, key_path)
    return key_path


def test_e1_db_scan_and_restart_are_plaintext_free(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, keyring_file: Path
) -> None:
    db_path = tmp_path / "investflow.db"
    monkeypatch.setenv(KEYRING_ENV, json.dumps({"v1": generate_key()}))
    monkeypatch.setenv("INVESTFLOW_ENC_KEY_FILE", str(keyring_file))
    monkeypatch.setenv("INVESTFLOW_ACTIVE_KEY_ID", "v1")

    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE account_sensitive ("
        "account_id INTEGER PRIMARY KEY, "
        "account_number_enc BLOB, "
        "key_id TEXT)"
    )
    plaintext = "1234-5678-9012-3456"
    blob = encrypt_field("account_sensitive", "account_number_enc", 1, plaintext, key_id="v1")
    conn.execute(
        "INSERT INTO account_sensitive (account_id, account_number_enc, key_id) VALUES (?, ?, ?)",
        (1, blob, "v1"),
    )
    conn.commit()
    conn.close()

    raw_db = db_path.read_bytes()
    wal = db_path.with_name(db_path.name + "-wal")
    if wal.exists():
        raw_db += wal.read_bytes()
    assert plaintext.encode() not in raw_db
    assert (
        decrypt_field("account_sensitive", "account_number_enc", 1, blob, key_id="v1") == plaintext
    )

    reloaded = load_keyring()
    assert (
        decrypt_field(
            "account_sensitive", "account_number_enc", 1, blob, keyring=reloaded, key_id="v1"
        )
        == plaintext
    )


def test_e2_aad_binding_rejects_ciphertext_copy_between_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVESTFLOW_ACTIVE_KEY_ID", "v1")
    monkeypatch.setenv("INVESTFLOW_ENC_KEYS", json.dumps({"v1": generate_key()}))

    a = encrypt_field("account_sensitive", "account_number_enc", 101, "1234-5678-90", key_id="v1")
    b = encrypt_field("account_sensitive", "account_number_enc", 102, "9999-1111-22", key_id="v1")
    with pytest.raises(DecryptError):
        decrypt_field("account_sensitive", "account_number_enc", 102, a, key_id="v1")
    assert (
        decrypt_field("account_sensitive", "account_number_enc", 101, a, key_id="v1")
        == "1234-5678-90"
    )
    assert (
        decrypt_field("account_sensitive", "account_number_enc", 102, b, key_id="v1")
        == "9999-1111-22"
    )


def test_e3_missing_keyfile_behaviour_returns_masked_non_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVESTFLOW_ACTIVE_KEY_ID", "v1")
    monkeypatch.setenv("INVESTFLOW_ENC_KEYS", json.dumps({"v1": generate_key()}))
    blob = encrypt_field("account_sensitive", "account_number_enc", 7, "1234-5678-90", key_id="v1")

    monkeypatch.setenv("INVESTFLOW_ENC_KEYS", json.dumps({"v2": generate_key()}))
    with pytest.raises(DecryptError):
        decrypt_field("account_sensitive", "account_number_enc", 7, blob, key_id="v1")

    masked = mask_secret("1234-5678-90")
    assert masked.startswith("•••")
    assert "1234-5678-90" not in masked


def test_e4_rotation_backfill_and_idempotence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, keyring_file: Path
) -> None:
    monkeypatch.setenv("INVESTFLOW_ENC_KEY_FILE", str(keyring_file))
    monkeypatch.setenv("INVESTFLOW_ACTIVE_KEY_ID", "v1")
    keyring = load_keyring()
    keyring["v2"] = generate_key()
    save_keyring(keyring, keyring_file)

    blobs = [
        encrypt_field("account_sensitive", "account_number_enc", 1, "1111", key_id="v1"),
        encrypt_field("account_sensitive", "account_number_enc", 2, "2222", key_id="v1"),
        encrypt_field("account_sensitive", "account_number_enc", 3, "3333", key_id="v1"),
    ]

    rotated = rotate_keyring("v2", keyring_path=keyring_file, db_path=tmp_path / "rot.db")
    assert rotated == "v2"
    assert get_active_key_id() == "v2"
    for idx, blob in enumerate(blobs, start=1):
        assert (
            decrypt_field("account_sensitive", "account_number_enc", idx, blob, key_id="v1")
            == str(idx) * 4
        )


def test_e5_log_safety_prevents_plaintext_in_logs(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("INVESTFLOW_ACTIVE_KEY_ID", "v1")
    monkeypatch.setenv("INVESTFLOW_ENC_KEYS", json.dumps({"v1": generate_key()}))
    blob = encrypt_field("account_sensitive", "account_number_enc", 5, "1234-5678-90", key_id="v1")
    monkeypatch.setenv("INVESTFLOW_ENC_KEYS", json.dumps({"v2": generate_key()}))
    with caplog.at_level("WARNING"):
        with pytest.raises(DecryptError):
            decrypt_field("account_sensitive", "account_number_enc", 5, blob, key_id="v1")
    assert "1234-5678-90" not in caplog.text
    assert str(blob) not in caplog.text


def test_e6_masking_hides_sensitive_value() -> None:
    masked = mask_secret("1234567890")
    assert masked.startswith("•••")
    assert masked.endswith("7890")
    assert "1234567890" not in masked


def test_e7_export_masking_keeps_default_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INVESTFLOW_ACTIVE_KEY_ID", "v1")
    monkeypatch.setenv("INVESTFLOW_ENC_KEYS", json.dumps({"v1": generate_key()}))
    masked = mask_secret("1234-5678-9012-3456")
    assert "1234-5678-9012-3456" not in masked
    assert masked.count("•") >= 3


def test_e8_codec_uses_random_nonce_and_unique_ciphertexts() -> None:
    payloads = [
        encrypt_field("account_sensitive", "account_number_enc", 9, "ABC-123", key_id="v1")
        for _ in range(100)
    ]
    assert len(set(payloads)) == len(payloads)
