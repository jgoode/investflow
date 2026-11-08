from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import CSRF_HEADER, register


def test_seeded_chart_of_accounts_is_present_and_idempotent(client: TestClient) -> None:
    register(client, "alice")

    first = client.get("/api/accounts/tree", headers=CSRF_HEADER)
    assert first.status_code == 200
    payload = first.json()
    root_names = {row["name"] for row in payload["tree"]}
    assert {"Assets", "Liabilities", "Income", "Expenses", "Equity"}.issubset(root_names)

    second = client.get("/api/accounts/tree", headers=CSRF_HEADER)
    assert second.status_code == 200
    second_payload = second.json()
    assert len(second_payload["tree"]) >= len(payload["tree"])


def test_create_edit_and_archive_account(client: TestClient) -> None:
    register(client, "alice")
    seed = client.get("/api/accounts/tree", headers=CSRF_HEADER)
    assets = next(row for row in seed.json()["tree"] if row["name"] == "Assets")

    created = client.post(
        "/api/accounts",
        headers=CSRF_HEADER,
        json={
            "code": "CHK-01",
            "name": "Checking",
            "type": "asset",
            "subtype": "bank",
            "parent_id": assets["id"],
            "institution": "Demo Bank",
            "description": "Primary checking",
            "is_investment": False,
            "account_number": "1234",
        },
    )
    assert created.status_code == 200, created.text
    account = created.json()["account"]
    assert account["code"] == "CHK-01"
    assert account["name"] == "Checking"
    assert account["is_archived"] is False

    updated = client.patch(
        f"/api/accounts/{account['id']}",
        headers=CSRF_HEADER,
        json={"name": "Checking Plus", "is_archived": True},
    )
    assert updated.status_code == 200
    assert updated.json()["account"]["name"] == "Checking Plus"
    assert updated.json()["account"]["is_archived"] is True
