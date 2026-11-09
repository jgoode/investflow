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


def test_run_report_cash_flow_and_net_worth_include_ledger_and_market_values(app_env: Path) -> None:
    ensure_seeded_coa()
    ensure_seeded_categories()
    with connect() as conn:
        bank_id = int(conn.execute("SELECT id FROM accounts WHERE code = 'BANK-01'").fetchone()[0])
        brokerage_id = int(
            conn.execute("SELECT id FROM accounts WHERE code = 'BROKERAGE-01'").fetchone()[0]
        )
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
            "date": "2026-03-02",
            "description": "Salary",
            "lines": [
                {
                    "account_id": bank_id,
                    "direction": "debit",
                    "amount_cents": 200_000,
                    "category_id": salary_category_id,
                },
                {
                    "account_id": salary_id,
                    "direction": "credit",
                    "amount_cents": 200_000,
                    "category_id": salary_category_id,
                },
            ],
        },
        created_by=None,
    )
    create_transaction(
        {
            "date": "2026-03-05",
            "description": "Groceries",
            "lines": [
                {
                    "account_id": food_id,
                    "direction": "debit",
                    "amount_cents": 50_000,
                    "category_id": food_category_id,
                },
                {
                    "account_id": bank_id,
                    "direction": "credit",
                    "amount_cents": 50_000,
                    "category_id": food_category_id,
                },
            ],
        },
        created_by=None,
    )

    with connect() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS positions ("
            "id INTEGER PRIMARY KEY, account_id INTEGER, ticker TEXT, "
            "quantity_q4 INTEGER, avg_cost_q4 INTEGER, status TEXT, "
            "realized_gain_loss_cents INTEGER, created_at INTEGER, "
            "updated_at INTEGER)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS price_cache ("
            "id INTEGER PRIMARY KEY, ticker TEXT, date TEXT, close_q4 INTEGER, "
            "volume INTEGER, source TEXT, fetched_at INTEGER)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS latest_quotes ("
            "ticker TEXT PRIMARY KEY, price_q4 INTEGER, asof TEXT, source TEXT, "
            "fetched_at INTEGER)"
        )
        conn.execute(
            (
                "INSERT INTO positions (account_id, ticker, quantity_q4, avg_cost_q4, "
                "status, realized_gain_loss_cents, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
            ),
            (brokerage_id, "AAPL", 10_0000, 1500000, "open", 0, 1700000000, 1700000000),
        )
        conn.execute(
            (
                "INSERT INTO price_cache (ticker, date, close_q4, volume, source, "
                "fetched_at) VALUES (?, ?, ?, ?, ?, ?)"
            ),
            ("AAPL", "2026-03-31", 1750000, 1000, "manual", 1700000000),
        )
        conn.execute(
            (
                "INSERT INTO latest_quotes (ticker, price_q4, asof, source, "
                "fetched_at) VALUES (?, ?, ?, ?, ?)"
            ),
            ("AAPL", 1750000, "2026-03-31", "manual", 1700000000),
        )
        conn.commit()

    cash_flow = run_report(
        "cash_flow",
        {"date_from": "2026-03-01", "date_to": "2026-03-31", "include_void": False},
    )
    assert cash_flow["totals"]["opening_net_liquid_cents"] == 0
    assert cash_flow["totals"]["inflow_cents"] == 200_000
    assert cash_flow["totals"]["outflow_cents"] == 50_000
    assert cash_flow["totals"]["closing_net_liquid_cents"] == 150_000

    net_worth = run_report(
        "net_worth",
        {"date_from": "2026-03-01", "date_to": "2026-03-31"},
    )
    assert net_worth["totals"]["net_worth_cents"] == 325_000
    assert net_worth["rows"][-1]["holdings_value_cents"] == 175_000
