from __future__ import annotations

import json

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
