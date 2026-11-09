from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from app.accounts import ensure_seeded_coa
from app.categories import ensure_seeded_categories
from app.db.connection import connect
from app.reports import run_report
from app.transactions import create_transaction


def test_run_report_rejects_unknown_kind(app_env: Path) -> None:
    with pytest.raises(HTTPException) as exc_info:
        run_report("unknown-kind", {})
    assert exc_info.value.status_code == 404


def test_run_report_monthly_is_deterministic_from_ledger(app_env: Path) -> None:
    ensure_seeded_coa()
    ensure_seeded_categories()
    with connect() as conn:
        bank_id = int(conn.execute("SELECT id FROM accounts WHERE code = 'BANK-01'").fetchone()[0])
        salary_id = int(
            conn.execute("SELECT id FROM accounts WHERE code = 'INCOME-SALARY'").fetchone()[0]
        )
        food_id = int(conn.execute("SELECT id FROM accounts WHERE code = 'EXP-FOOD'").fetchone()[0])
        salary_category_id = int(
            conn.execute("SELECT id FROM categories WHERE name = 'Salary'").fetchone()[0]
        )
        food_category_id = int(
            conn.execute("SELECT id FROM categories WHERE name = 'Food'").fetchone()[0]
        )

    create_transaction(
        {
            "date": "2026-03-10",
            "description": "Income",
            "lines": [
                {
                    "account_id": bank_id,
                    "direction": "debit",
                    "amount_cents": 90_000,
                    "category_id": salary_category_id,
                },
                {
                    "account_id": salary_id,
                    "direction": "credit",
                    "amount_cents": 90_000,
                    "category_id": salary_category_id,
                },
            ],
        },
        created_by=None,
    )
    create_transaction(
        {
            "date": "2026-03-11",
            "description": "Expense",
            "lines": [
                {
                    "account_id": food_id,
                    "direction": "debit",
                    "amount_cents": 20_000,
                    "category_id": food_category_id,
                },
                {
                    "account_id": bank_id,
                    "direction": "credit",
                    "amount_cents": 20_000,
                    "category_id": food_category_id,
                },
            ],
        },
        created_by=None,
    )

    report = run_report(
        "monthly",
        {"date_from": "2026-03-01", "date_to": "2026-03-31", "months": "2026-03"},
    )
    assert report["rows"] == [
        {
            "period": "2026-03",
            "income_cents": 90_000,
            "expense_cents": 20_000,
            "net_cents": 70_000,
            "top_expense_categories": [{"category_name": "Food", "amount_cents": 20_000}],
        }
    ]
    assert report["integrity"]["matches"] is True
