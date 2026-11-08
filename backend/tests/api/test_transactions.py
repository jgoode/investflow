from __future__ import annotations

import json
import sqlite3

from fastapi.testclient import TestClient

from app.crypto_store import write_account_sensitive
from tests.conftest import CSRF_HEADER, register


def _account_id_by_code(client: TestClient, code: str) -> int:
    payload = client.get("/api/accounts", headers=CSRF_HEADER).json()
    row = next(item for item in payload["accounts"] if item["code"] == code)
    return int(row["id"])


def _expense_category_id(client: TestClient) -> int:
    payload = client.get("/api/categories", headers=CSRF_HEADER).json()
    row = next(item for item in payload["categories"] if item["flow"] == "expense")
    return int(row["id"])


def test_quick_expense_post_balances_and_rejects_imbalance(client: TestClient) -> None:
    register(client, "alice")
    bank_id = _account_id_by_code(client, "BANK-01")
    category_id = _expense_category_id(client)

    created = client.post(
        "/api/transactions",
        headers=CSRF_HEADER,
        json={
            "date": "2026-11-08",
            "description": "Groceries",
            "mode": "expense",
            "account_id": bank_id,
            "category_id": category_id,
            "amount_cents": 2500,
        },
    )
    assert created.status_code == 200, created.text
    tx = created.json()["transaction"]
    assert tx["description"] == "Groceries"
    assert len(tx["lines"]) == 2
    assert sum(line["amount_cents"] for line in tx["lines"] if line["direction"] == "debit") == 2500
    assert (
        sum(line["amount_cents"] for line in tx["lines"] if line["direction"] == "credit") == 2500
    )

    imbalance = client.post(
        "/api/transactions",
        headers=CSRF_HEADER,
        json={
            "date": "2026-11-08",
            "description": "Broken groceries",
            "lines": [
                {
                    "account_id": _account_id_by_code(client, "EXP-FOOD"),
                    "direction": "debit",
                    "amount_cents": 2000,
                },
                {"account_id": bank_id, "direction": "credit", "amount_cents": 1500},
            ],
        },
    )
    assert imbalance.status_code == 422, imbalance.text
    assert "balance" in imbalance.text.lower()


def test_transaction_list_masks_account_number_and_applies_filters(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setenv(
        "INVESTFLOW_ENC_KEYS", json.dumps({"v1": "mO4v8f2W4iD5n0V2Q2bM8I+N3Y8xgS2GUDV5Wn9m6xg="})
    )
    monkeypatch.setenv("INVESTFLOW_ACTIVE_KEY_ID", "v1")
    register(client, "alice")
    bank_id = _account_id_by_code(client, "BANK-01")
    write_account_sensitive(bank_id, {"account_number_enc": "1234-5678-9012-3456"})

    category_id = _expense_category_id(client)
    created = client.post(
        "/api/transactions",
        headers=CSRF_HEADER,
        json={
            "date": "2026-11-08",
            "description": "Groceries",
            "mode": "expense",
            "account_id": bank_id,
            "category_id": category_id,
            "amount_cents": 1500,
        },
    )
    assert created.status_code == 200, created.text

    rows = client.get(
        f"/api/transactions?account_id={bank_id}&date_from=2026-11-01&date_to=2026-11-30",
        headers=CSRF_HEADER,
    )
    assert rows.status_code == 200, rows.text
    payload = rows.json()
    assert payload["page"] == 1
    assert payload["transactions"]
    line = payload["transactions"][0]["lines"][0]
    assert line["account_number_mask"].startswith("•••")
    assert "1234" not in json.dumps(payload)


def test_transfer_post_supports_two_account_move_and_running_balance(client: TestClient) -> None:
    register(client, "alice")
    source_id = _account_id_by_code(client, "BANK-01")
    created = client.post(
        "/api/accounts",
        headers=CSRF_HEADER,
        json={
            "code": "BANK-02",
            "name": "Bank B",
            "type": "asset",
            "subtype": "bank",
            "parent_id": _account_id_by_code(client, "BANK-GROUP"),
            "institution": "Demo Bank",
            "description": "Second bank account",
        },
    )
    assert created.status_code == 200, created.text
    target_id = created.json()["account"]["id"]

    created = client.post(
        "/api/transactions",
        headers=CSRF_HEADER,
        json={
            "date": "2026-11-08",
            "description": "House transfer",
            "mode": "transfer",
            "account_id": source_id,
            "target_account_id": target_id,
            "amount_cents": 2500,
        },
    )
    assert created.status_code == 200, created.text
    tx = created.json()["transaction"]
    assert tx["description"] == "House transfer"
    assert len(tx["lines"]) == 2
    assert sum(line["amount_cents"] for line in tx["lines"] if line["direction"] == "debit") == 2500
    assert (
        sum(line["amount_cents"] for line in tx["lines"] if line["direction"] == "credit") == 2500
    )

    rows = client.get(
        f"/api/transactions?account_id={source_id}&date_from=2026-11-01&date_to=2026-11-30",
        headers=CSRF_HEADER,
    )
    assert rows.status_code == 200, rows.text
    payload = rows.json()
    assert payload["transactions"]
    assert payload["transactions"][0]["running_balance_cents"] is not None


def test_edit_and_void_transaction_workflow_keeps_audit_and_voids_hidden_by_default(
    client: TestClient,
) -> None:
    register(client, "alice")
    bank_id = _account_id_by_code(client, "BANK-01")
    expense_id = _account_id_by_code(client, "EXP-FOOD")
    category_id = _expense_category_id(client)

    created = client.post(
        "/api/transactions",
        headers=CSRF_HEADER,
        json={
            "date": "2026-11-08",
            "description": "Groceries",
            "mode": "expense",
            "account_id": bank_id,
            "category_id": category_id,
            "amount_cents": 1500,
        },
    )
    assert created.status_code == 200, created.text
    tx_id = created.json()["transaction"]["id"]

    updated = client.patch(
        f"/api/transactions/{tx_id}",
        headers=CSRF_HEADER,
        json={
            "description": "Groceries revised",
            "lines": [
                {"account_id": bank_id, "direction": "debit", "amount_cents": 1800},
                {"account_id": expense_id, "direction": "credit", "amount_cents": 1800},
            ],
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["transaction"]["description"] == "Groceries revised"

    voided = client.post(f"/api/transactions/{tx_id}/void", headers=CSRF_HEADER, json={})
    assert voided.status_code == 200, voided.text
    assert voided.json()["transaction"]["status"] == "void"

    default_rows = client.get(
        "/api/transactions?date_from=2026-11-01&date_to=2026-11-30", headers=CSRF_HEADER
    )
    assert default_rows.status_code == 200, default_rows.text
    assert all(item["id"] != tx_id for item in default_rows.json()["transactions"])

    include_void_rows = client.get(
        "/api/transactions?include_void=true&date_from=2026-11-01&date_to=2026-11-30",
        headers=CSRF_HEADER,
    )
    assert include_void_rows.status_code == 200, include_void_rows.text
    assert any(item["id"] == tx_id for item in include_void_rows.json()["transactions"])

    blocked = client.patch(
        f"/api/transactions/{tx_id}",
        headers=CSRF_HEADER,
        json={
            "description": "Nope",
            "lines": [
                {"account_id": bank_id, "direction": "debit", "amount_cents": 12},
                {"account_id": expense_id, "direction": "credit", "amount_cents": 12},
            ],
        },
    )
    assert blocked.status_code == 422, blocked.text
    assert "void" in blocked.text.lower()

    conn = sqlite3.connect(client.app.state.db_path)
    try:
        rows = conn.execute(
            "SELECT action FROM audit_log WHERE action IN ('tx.post', 'tx.edit', 'tx.void')"
        ).fetchall()
    finally:
        conn.close()
    assert rows
