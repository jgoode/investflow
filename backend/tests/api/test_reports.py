from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from tests.conftest import CSRF_HEADER, register


def _account_id_by_code(client: TestClient, code: str) -> int:
    payload = client.get("/api/accounts", headers=CSRF_HEADER).json()
    row = next(item for item in payload["accounts"] if item["code"] == code)
    return int(row["id"])


def _category_id_by_name(client: TestClient, name: str) -> int:
    payload = client.get("/api/categories", headers=CSRF_HEADER).json()
    row = next(item for item in payload["categories"] if item["name"] == name)
    return int(row["id"])


def _post_lines(
    client: TestClient, *, date: str, description: str, lines: list[dict[str, object]]
) -> None:
    created = client.post(
        "/api/transactions",
        headers=CSRF_HEADER,
        json={"date": date, "description": description, "lines": lines},
    )
    assert created.status_code == 200, created.text


def _post_quick(
    client: TestClient,
    *,
    date: str,
    description: str,
    mode: str,
    account_id: int,
    category_id: int,
    amount_cents: int,
) -> int:
    created = client.post(
        "/api/transactions",
        headers=CSRF_HEADER,
        json={
            "date": date,
            "description": description,
            "mode": mode,
            "account_id": account_id,
            "category_id": category_id,
            "amount_cents": amount_cents,
        },
    )
    assert created.status_code == 200, created.text
    return int(created.json()["transaction"]["id"])


def _void_transaction(client: TestClient, tx_id: int) -> None:
    response = client.post(f"/api/transactions/{tx_id}/void", headers=CSRF_HEADER, json={})
    assert response.status_code == 200, response.text


def test_reports_require_authentication(client: TestClient) -> None:
    response = client.get("/api/reports/coa")
    assert response.status_code == 401


def test_coa_report_groups_accounts_and_balances_from_transaction_lines(client: TestClient) -> None:
    register(client, "alice")
    bank_id = _account_id_by_code(client, "BANK-01")
    equity_id = _account_id_by_code(client, "EQUITY-OPEN")

    _post_lines(
        client,
        date="2026-01-05",
        description="Opening balance",
        lines=[
            {"account_id": bank_id, "direction": "debit", "amount_cents": 100_000},
            {"account_id": equity_id, "direction": "credit", "amount_cents": 100_000},
        ],
    )

    created = client.post(
        "/api/accounts",
        headers=CSRF_HEADER,
        json={
            "code": "ARCH-TEST",
            "name": "Archived test",
            "type": "asset",
            "subtype": "bank",
            "parent_id": _account_id_by_code(client, "BANK-GROUP"),
            "institution": "Demo",
            "description": "report coverage",
        },
    )
    assert created.status_code == 200, created.text
    archived_id = int(created.json()["account"]["id"])
    archived = client.patch(
        f"/api/accounts/{archived_id}",
        headers=CSRF_HEADER,
        json={"is_archived": True},
    )
    assert archived.status_code == 200, archived.text

    response = client.get("/api/reports/coa?as_of=2026-01-31", headers=CSRF_HEADER)
    assert response.status_code == 200, response.text
    payload = response.json()["report"]

    assert payload["kind"] == "coa"
    assert payload["params"]["as_of"] == "2026-01-31"
    rows = payload["rows"]
    assert any(row["code"] == "ARCH-TEST" and row["is_archived"] is True for row in rows)
    assert any(row["code"] == "BANK-01" and row["balance_cents"] == 100_000 for row in rows)
    assert any(row["code"] == "EQUITY-OPEN" and row["balance_cents"] == 100_000 for row in rows)
    assert payload["totals"]["balance_sheet_delta_cents"] == 0


def test_summary_report_filters_range_and_excludes_void_by_default(client: TestClient) -> None:
    register(client, "alice")
    bank_id = _account_id_by_code(client, "BANK-01")
    salary_category_id = _category_id_by_name(client, "Salary")
    food_category_id = _category_id_by_name(client, "Food")

    _post_quick(
        client,
        date="2026-02-03",
        description="Salary",
        mode="income",
        account_id=bank_id,
        category_id=salary_category_id,
        amount_cents=200_000,
    )
    _post_quick(
        client,
        date="2026-02-05",
        description="Groceries",
        mode="expense",
        account_id=bank_id,
        category_id=food_category_id,
        amount_cents=50_000,
    )
    void_id = _post_quick(
        client,
        date="2026-02-06",
        description="Voided groceries",
        mode="expense",
        account_id=bank_id,
        category_id=food_category_id,
        amount_cents=10_000,
    )
    _void_transaction(client, void_id)

    response = client.get(
        "/api/reports/summary?date_from=2026-02-01&date_to=2026-02-28",
        headers=CSRF_HEADER,
    )
    assert response.status_code == 200, response.text
    report = response.json()["report"]
    assert report["kind"] == "summary"
    assert report["params"]["include_void"] is False
    assert report["totals"]["income_cents"] == 200_000
    assert report["totals"]["expense_cents"] == 50_000
    assert report["totals"]["surplus_cents"] == 150_000
    assert any(item["category_name"] == "Salary" for item in report["income_categories"])
    assert any(item["category_name"] == "Food" for item in report["expense_categories"])

    response_with_void = client.get(
        "/api/reports/summary?date_from=2026-02-01&date_to=2026-02-28&include_void=true",
        headers=CSRF_HEADER,
    )
    assert response_with_void.status_code == 200, response_with_void.text
    totals_with_void = response_with_void.json()["report"]["totals"]
    assert totals_with_void["expense_cents"] == 60_000
    assert totals_with_void["surplus_cents"] == 140_000


def test_monthly_report_and_integrity_reaggregation_match_raw_lines(
    client: TestClient, app_env: Path
) -> None:
    register(client, "alice")
    bank_id = _account_id_by_code(client, "BANK-01")
    salary_category_id = _category_id_by_name(client, "Salary")
    food_category_id = _category_id_by_name(client, "Food")
    housing_category_id = _category_id_by_name(client, "Housing")

    _post_quick(
        client,
        date="2026-01-10",
        description="Salary Jan",
        mode="income",
        account_id=bank_id,
        category_id=salary_category_id,
        amount_cents=100_000,
    )
    _post_quick(
        client,
        date="2026-01-12",
        description="Groceries Jan",
        mode="expense",
        account_id=bank_id,
        category_id=food_category_id,
        amount_cents=30_000,
    )
    _post_quick(
        client,
        date="2026-02-03",
        description="Salary Feb",
        mode="income",
        account_id=bank_id,
        category_id=salary_category_id,
        amount_cents=120_000,
    )
    _post_quick(
        client,
        date="2026-02-11",
        description="Housing Feb",
        mode="expense",
        account_id=bank_id,
        category_id=housing_category_id,
        amount_cents=40_000,
    )

    report_response = client.get(
        "/api/reports/monthly?date_from=2026-01-01&date_to=2026-02-28&months=2026-01,2026-02",
        headers=CSRF_HEADER,
    )
    assert report_response.status_code == 200, report_response.text
    report = report_response.json()["report"]
    assert report["kind"] == "monthly"
    assert report["params"]["months"] == ["2026-01", "2026-02"]
    assert "date_from=2026-01-01" in report["query"]
    assert "months=2026-01%2C2026-02" in report["query"]
    assert report["integrity"]["matches"] is True

    rows = {row["period"]: row for row in report["rows"]}
    assert rows["2026-01"]["income_cents"] == 100_000
    assert rows["2026-01"]["expense_cents"] == 30_000
    assert rows["2026-01"]["net_cents"] == 70_000
    assert rows["2026-02"]["income_cents"] == 120_000
    assert rows["2026-02"]["expense_cents"] == 40_000
    assert rows["2026-02"]["net_cents"] == 80_000
    assert rows["2026-01"]["top_expense_categories"][0]["category_name"] == "Food"
    assert rows["2026-02"]["top_expense_categories"][0]["category_name"] == "Housing"

    with sqlite3.connect(app_env) as conn:
        raw_income_rows = conn.execute(
            """
            SELECT substr(t.date, 1, 7) AS month, SUM(tl.amount_cents) AS income_cents
            FROM transaction_lines tl
            JOIN transactions t ON t.id = tl.transaction_id
            JOIN accounts a ON a.id = tl.account_id
            WHERE t.status = 'posted'
              AND t.date >= '2026-01-01'
              AND t.date <= '2026-02-28'
              AND a.type = 'income'
              AND tl.direction = 'credit'
            GROUP BY substr(t.date, 1, 7)
            """
        ).fetchall()
    raw_income = {str(month): int(amount) for month, amount in raw_income_rows}
    assert raw_income == {month: int(row["income_cents"]) for month, row in rows.items()}


def test_quarterly_report_supports_year_filter_and_optional_accounts_subreport(
    client: TestClient,
) -> None:
    register(client, "alice")
    bank_id = _account_id_by_code(client, "BANK-01")
    salary_category_id = _category_id_by_name(client, "Salary")
    food_category_id = _category_id_by_name(client, "Food")

    _post_quick(
        client,
        date="2026-01-15",
        description="Salary Q1",
        mode="income",
        account_id=bank_id,
        category_id=salary_category_id,
        amount_cents=100_000,
    )
    _post_quick(
        client,
        date="2026-04-15",
        description="Salary Q2",
        mode="income",
        account_id=bank_id,
        category_id=salary_category_id,
        amount_cents=110_000,
    )
    _post_quick(
        client,
        date="2026-04-20",
        description="Food Q2",
        mode="expense",
        account_id=bank_id,
        category_id=food_category_id,
        amount_cents=45_000,
    )

    response = client.get(
        "/api/reports/quarterly?year=2026&include_accounts=true",
        headers=CSRF_HEADER,
    )
    assert response.status_code == 200, response.text
    report = response.json()["report"]
    assert report["kind"] == "quarterly"
    assert report["params"]["year"] == 2026
    assert report["params"]["include_accounts"] is True

    rows = {row["period"]: row for row in report["rows"]}
    assert rows["2026-Q1"]["income_cents"] == 100_000
    assert rows["2026-Q1"]["expense_cents"] == 0
    assert rows["2026-Q2"]["income_cents"] == 110_000
    assert rows["2026-Q2"]["expense_cents"] == 45_000
    assert rows["2026-Q2"]["net_cents"] == 65_000
    assert "accounts" in rows["2026-Q2"]
