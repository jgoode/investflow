from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from tests.conftest import CSRF_HEADER, register


def _id_by_code(client: TestClient, code: str) -> int:
    payload = client.get("/api/accounts", headers=CSRF_HEADER).json()
    row = next(item for item in payload["accounts"] if item["code"] == code)
    return int(row["id"])


def test_seeded_categories_are_present_and_idempotent(client: TestClient) -> None:
    register(client, "alice")

    first = client.get("/api/categories", headers=CSRF_HEADER)
    assert first.status_code == 200
    first_rows = first.json()["categories"]
    assert any(row["name"] == "Salary" and row["flow"] == "income" for row in first_rows)
    assert any(row["name"] == "Housing" and row["flow"] == "expense" for row in first_rows)

    second = client.get("/api/categories", headers=CSRF_HEADER)
    assert second.status_code == 200
    second_rows = second.json()["categories"]
    assert len(second_rows) == len(first_rows)
    assert {(row["name"], row["flow"]) for row in second_rows} == {
        (row["name"], row["flow"]) for row in first_rows
    }


def test_create_edit_assign_and_delete_category_with_history_safe_fallback(
    client: TestClient, app_env: Path
) -> None:
    register(client, "alice")
    income_account_id = _id_by_code(client, "INCOME-SALARY")

    created = client.post(
        "/api/categories",
        headers=CSRF_HEADER,
        json={
            "name": "Bonus",
            "flow": "income",
            "color": "#22aa66",
            "default_account_id": income_account_id,
        },
    )
    assert created.status_code == 200, created.text
    category = created.json()["category"]
    assert category["name"] == "Bonus"
    assert category["default_account_id"] == income_account_id

    line_id = _insert_demo_line(app_env)
    assigned = client.patch(
        f"/api/categories/lines/{line_id}",
        headers=CSRF_HEADER,
        json={"category_id": category["id"]},
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["line"]["category_id"] == category["id"]

    updated = client.patch(
        f"/api/categories/{category['id']}",
        headers=CSRF_HEADER,
        json={"name": "Annual Bonus", "color": "#00aa44"},
    )
    assert updated.status_code == 200
    assert updated.json()["category"]["name"] == "Annual Bonus"
    assert updated.json()["category"]["color"] == "#00aa44"

    refused = client.delete(f"/api/categories/{category['id']}", headers=CSRF_HEADER)
    assert refused.status_code == 422

    deleted = client.request(
        "DELETE",
        f"/api/categories/{category['id']}",
        headers={**CSRF_HEADER, "Content-Type": "application/json"},
        json={"confirm": True},
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["status"] == "ok"

    with sqlite3.connect(app_env) as conn:
        row = conn.execute(
            "SELECT category_id FROM transaction_lines WHERE id = ?", (line_id,)
        ).fetchone()
    assert row is not None and row[0] is None


def test_category_default_account_must_match_flow(client: TestClient) -> None:
    register(client, "alice")
    income_account_id = _id_by_code(client, "INCOME-SALARY")

    invalid = client.post(
        "/api/categories",
        headers=CSRF_HEADER,
        json={
            "name": "Groceries",
            "flow": "expense",
            "default_account_id": income_account_id,
        },
    )
    assert invalid.status_code == 422
    assert "flow" in invalid.text.lower()


def _insert_demo_line(db_path: Path) -> int:
    with sqlite3.connect(db_path) as conn:
        tx_cursor = conn.execute(
            "INSERT INTO transactions "
            "(date, description, reference, status, created_by, created_at, updated_at) "
            "VALUES ('2026-11-08', 'seeded line', NULL, 'posted', 1, 0, 0)"
        )
        tx_id = int(tx_cursor.lastrowid)
        line_cursor = conn.execute(
            "INSERT INTO transaction_lines "
            "(transaction_id, account_id, direction, amount_cents, memo, category_id) "
            "VALUES (?, ?, 'credit', 1000, 'line', NULL)",
            (tx_id, 1),
        )
        conn.commit()
        return int(line_cursor.lastrowid)
