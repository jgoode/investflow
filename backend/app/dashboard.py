from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any
from urllib.parse import urlencode

from app.db.connection import connect
from app.reports import run_report
from app.transactions import list_transactions


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _previous_month_start(value: date) -> date:
    month = value.month - 1
    year = value.year
    if month == 0:
        month = 12
        year -= 1
    return date(year, month, 1)


def _month_range(value: date) -> tuple[str, str]:
    month_start = _month_start(value)
    if month_start.month == 12:
        next_month = date(month_start.year + 1, 1, 1)
    else:
        next_month = date(month_start.year, month_start.month + 1, 1)
    return month_start.isoformat(), (next_month - timedelta(days=1)).isoformat()


def _build_href(kind: str, params: dict[str, Any]) -> str:
    return f"/reports/{kind}?{urlencode(params)}"


def _safe_pct_change(current: int, previous: int) -> float:
    if previous == 0:
        return 0.0 if current == 0 else 100.0
    return round(((current - previous) / abs(previous)) * 100, 2)


def _empty_book() -> bool:
    with connect() as conn:
        tx_count = int(
            conn.execute("SELECT COUNT(*) FROM transactions WHERE status != 'void'").fetchone()[0]
        )
        position_count = int(conn.execute("SELECT COUNT(*) FROM positions").fetchone()[0])
    return tx_count == 0 and position_count == 0


def _account_summary() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT a.type, a.subtype, COALESCE(SUM(CASE
                WHEN tl.direction = 'debit' THEN tl.amount_cents
                WHEN tl.direction = 'credit' THEN -tl.amount_cents
                ELSE 0
            END), 0) AS balance_cents
            FROM accounts a
            LEFT JOIN transaction_lines tl ON tl.account_id = a.id
            LEFT JOIN transactions t ON t.id = tl.transaction_id AND t.status = 'posted'
            GROUP BY a.id, a.type, a.subtype
            ORDER BY a.type ASC, a.name ASC
            """
        ).fetchall()
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        account_type = str(row["type"])
        balance = int(row["balance_cents"] or 0)
        if account_type in {"asset", "liability"}:
            grouped[account_type].append(
                {"type": account_type, "subtype": row["subtype"], "balance_cents": balance}
            )
    summary: list[dict[str, Any]] = []
    for account_type in ("asset", "liability"):
        entries = grouped.get(account_type, [])
        summary.append(
            {
                "type": account_type,
                "balance_cents": sum(item["balance_cents"] for item in entries),
                "items": entries[:4],
            }
        )
    return summary


def get_dashboard_payload() -> dict[str, Any]:
    today = date.today()
    month_start = _month_start(today)
    previous_month = _previous_month_start(today)
    previous_month_end = (month_start - timedelta(days=1)).isoformat()
    month_start_iso = month_start.isoformat()
    six_months_ago = month_start.replace(day=1) - timedelta(days=1)
    six_month_anchor = six_months_ago
    for _ in range(5):
        six_month_anchor = _previous_month_start(six_month_anchor)
    six_month_start = six_month_anchor.isoformat()

    net_worth_series = run_report(
        "net_worth",
        {"date_from": (today - timedelta(days=30)).isoformat(), "date_to": today.isoformat()},
    )
    net_worth_rows = net_worth_series.get("rows") or []
    current_net_worth = int(net_worth_rows[-1]["net_worth_cents"]) if net_worth_rows else 0
    previous_net_worth = (
        int(net_worth_rows[-2]["net_worth_cents"]) if len(net_worth_rows) >= 2 else 0
    )
    holdings_value = int(net_worth_rows[-1]["holdings_value_cents"]) if net_worth_rows else 0

    cash_flow_curr = run_report(
        "cash_flow", {"date_from": month_start_iso, "date_to": today.isoformat()}
    )
    cash_flow_prev = run_report(
        "cash_flow",
        {"date_from": previous_month.isoformat(), "date_to": previous_month_end},
    )
    inflow_curr = int(cash_flow_curr.get("totals", {}).get("inflow_cents", 0))
    outflow_curr = int(cash_flow_curr.get("totals", {}).get("outflow_cents", 0))
    inflow_prev = int(cash_flow_prev.get("totals", {}).get("inflow_cents", 0))
    outflow_prev = int(cash_flow_prev.get("totals", {}).get("outflow_cents", 0))

    monthly = run_report("monthly", {"date_from": six_month_start, "date_to": today.isoformat()})
    monthly_rows = monthly.get("rows") or []
    incomes_by_month = [
        {
            "period": row.get("period"),
            "income_cents": int(row.get("income_cents", 0)),
            "expense_cents": int(row.get("expense_cents", 0)),
        }
        for row in monthly_rows
    ]

    recent = list_transactions(
        date_from=(today - timedelta(days=90)).isoformat(),
        date_to=today.isoformat(),
        page=1,
        page_size=5,
        include_void=False,
    )
    recent_items = []
    for tx in recent.get("transactions", []):
        amount = 0
        for line in tx.get("lines", []):
            amount += int(line.get("amount_cents", 0))
        recent_items.append(
            {
                "id": int(tx["id"]),
                "date": tx["date"],
                "description": tx["description"],
                "amount_cents": amount // 2 if tx.get("lines") else amount,
                "status": tx.get("status"),
            }
        )

    empty = _empty_book()
    default_range = {
        "date_from": (today - timedelta(days=30)).isoformat(),
        "date_to": today.isoformat(),
    }
    monthly_range = {
        "date_from": six_month_start,
        "date_to": today.isoformat(),
    }
    recent_range = {
        "date_from": (today - timedelta(days=90)).isoformat(),
        "date_to": today.isoformat(),
    }
    response = {
        "dashboard": {
            "empty": empty,
            "cards": {
                "net_worth": {
                    "title": "Net worth",
                    "value_cents": current_net_worth,
                    "delta_pct": _safe_pct_change(current_net_worth, previous_net_worth),
                    "href": _build_href("net_worth", default_range),
                },
                "cash_flow": {
                    "title": "Cash flow",
                    "inflow_cents": inflow_curr,
                    "outflow_cents": outflow_curr,
                    "delta_pct": _safe_pct_change(
                        inflow_curr - outflow_curr, inflow_prev - outflow_prev
                    ),
                    "href": _build_href(
                        "cash_flow",
                        {"date_from": month_start_iso, "date_to": today.isoformat()},
                    ),
                },
                "income_expense": {
                    "title": "Income / expense",
                    "items": incomes_by_month,
                    "href": _build_href("monthly", monthly_range),
                },
                "holdings": {
                    "title": "Portfolio holdings",
                    "value_cents": holdings_value,
                    "href": _build_href("net_worth", default_range),
                },
                "recent_transactions": {
                    "title": "Recent activity",
                    "items": recent_items,
                    "href": f"/transactions?{urlencode(recent_range)}",
                },
                "accounts_summary": {
                    "title": "Accounts",
                    "items": _account_summary(),
                    "href": "/accounts",
                },
            },
            "empty_state": {
                "enabled": empty,
                "title": "Start your book",
                "message": (
                    "Add an account, post a transaction, or begin with the starter "
                    "chart of accounts."
                ),
            },
        }
    }
    return response
