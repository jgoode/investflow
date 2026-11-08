from __future__ import annotations

import logging
import os
from collections.abc import Iterable, Mapping

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from crypto.keyring import get_active_key_id, load_keyring

logger = logging.getLogger(__name__)

ENCRYPTED_FIELDS = {
    "account_sensitive": {
        "account_number_enc": "account_number",
        "routing_transit_enc": "routing_transit",
        "transfer_numbers_enc": "transfer_numbers",
        "notes_enc": "notes",
    }
}


class DecryptError(RuntimeError):
    """Raised when a ciphertext cannot be decrypted."""


def _aad(table_name: str, field_name: str, entity_id: int) -> bytes:
    return f"a:{table_name}:{field_name}:{entity_id}".encode()


def _mask_digits(value: str, keep: int = 4) -> str:
    if not value:
        return "•••"
    suffix = value[-keep:] if len(value) > keep else value
    return f"•••{suffix}"


def mask_secret(value: str | None, *, keep: int = 4) -> str:
    if value is None:
        return "•••"
    return _mask_digits(value, keep=keep)


def encrypt_field(
    table_name: str,
    field_name: str,
    entity_id: int,
    plaintext: str | None,
    *,
    key_id: str | None = None,
    keyring: Mapping[str, bytes] | None = None,
) -> bytes:
    if plaintext is None:
        return b""
    active_keyring = dict(keyring) if keyring is not None else load_keyring()
    chosen_key_id = key_id or get_active_key_id()
    if chosen_key_id not in active_keyring:
        raise KeyError(f"Unknown key id {chosen_key_id!r}")
    nonce = os.urandom(12)
    key = active_keyring[chosen_key_id]
    ciphertext = AESGCM(key).encrypt(
        nonce,
        plaintext.encode("utf-8"),
        _aad(table_name, field_name, entity_id),
    )
    payload = bytearray()
    payload.append(0x01)
    payload.append(len(chosen_key_id.encode("ascii")))
    payload.extend(chosen_key_id.encode("ascii"))
    payload.extend(nonce)
    payload.extend(ciphertext)
    return bytes(payload)


def decrypt_field(
    table_name: str,
    field_name: str,
    entity_id: int,
    blob: bytes | None,
    *,
    key_id: str | None = None,
    keyring: Mapping[str, bytes] | None = None,
    allow_missing: bool = False,
) -> str | None:
    if blob in (None, b""):
        return None

    if len(blob) < 14:
        if allow_missing:
            return None
        raise DecryptError("ciphertext too short")

    payload_version = blob[0]
    key_id_len = blob[1]
    if payload_version != 0x01:
        if allow_missing:
            return None
        raise DecryptError("unsupported ciphertext version")
    if len(blob) < 2 + key_id_len + 12 + 16:
        if allow_missing:
            return None
        raise DecryptError("ciphertext truncated")

    encoded_key_id = blob[2 : 2 + key_id_len].decode("ascii", errors="strict")
    nonce = blob[2 + key_id_len : 2 + key_id_len + 12]
    ciphertext = blob[2 + key_id_len + 12 :]
    active_keyring = dict(keyring) if keyring is not None else load_keyring()

    candidates: Iterable[str]
    if key_id is not None:
        candidates = [key_id, encoded_key_id, *sorted(active_keyring)]
    else:
        candidates = [encoded_key_id, *sorted(active_keyring)]
    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate not in active_keyring:
            continue
        try:
            payload = AESGCM(active_keyring[candidate]).decrypt(
                nonce,
                ciphertext,
                _aad(table_name, field_name, entity_id),
            )
            return payload.decode("utf-8")
        except Exception:
            continue

    logger.warning(
        "crypto decrypt failed for %s.%s(%s) key_id=%s ciphertext_len=%d",
        table_name,
        field_name,
        entity_id,
        key_id or encoded_key_id,
        len(blob),
    )
    if allow_missing:
        return None
    raise DecryptError(f"unable to decrypt {table_name}.{field_name} for entity {entity_id}")
