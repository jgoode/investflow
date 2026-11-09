from __future__ import annotations

import io
import zipfile
from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any
from urllib.parse import urlencode

from fastapi import HTTPException, status

from app.accounts import ensure_seeded_coa
from app.categories import ensure_seeded_categories
from app.db.connection import connect
from app.transactions import ensure_transactions_tables

REPORT_KINDS = {"coa", "summary", "monthly", "quarterly", "cash_flow", "net_worth"}
ACCOUNT_TYPES = {"asset", "liability", "income", "expense", "equity"}


@dataclass(frozen=True)
class ReportRange:
    date_from: str
    date_to: str


def _today() -> date:
    return date.today()


def _parse_iso_date(value: str, *, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{field} must use ISO format YYYY-MM-DD",
        ) from exc


def _parse_bool(value: str | bool | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    return normalized in {"1", "true", "yes"}


def _default_range() -> ReportRange:
    today = _today()
    start = today.replace(day=1) - timedelta(days=365)
    return ReportRange(date_from=start.isoformat(), date_to=today.isoformat())


def _parse_range_params(params: dict[str, Any]) -> ReportRange:
    default_range = _default_range()
    date_from = str(params.get("date_from") or default_range.date_from)
    date_to = str(params.get("date_to") or default_range.date_to)
    start = _parse_iso_date(date_from, field="date_from")
    end = _parse_iso_date(date_to, field="date_to")
    if start > end:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="date_from must be less than or equal to date_to",
        )
    return ReportRange(date_from=start.isoformat(), date_to=end.isoformat())


def _signed_for_account_type(*, account_type: str, direction: str, amount_cents: int) -> int:
    direction_sign = 1 if direction == "debit" else -1
    if account_type in {"liability", "income", "equity"}:
        direction_sign *= -1
    return direction_sign * amount_cents


def _income_expense_contribution(*, account_type: str, direction: str, amount_cents: int) -> int:
    if account_type == "income":
        return amount_cents if direction == "credit" else -amount_cents
    if account_type == "expense":
        return amount_cents if direction == "debit" else -amount_cents
    return 0


def _month_periods(date_from: str, date_to: str) -> list[str]:
    start = _parse_iso_date(date_from, field="date_from")
    end = _parse_iso_date(date_to, field="date_to")
    cursor = date(start.year, start.month, 1)
    stop = date(end.year, end.month, 1)
    periods: list[str] = []
    while cursor <= stop:
        periods.append(f"{cursor.year:04d}-{cursor.month:02d}")
        next_month = cursor.month + 1
        next_year = cursor.year
        if next_month == 13:
            next_month = 1
            next_year += 1
        cursor = date(next_year, next_month, 1)
    return periods


def _quarter_from_month(period: str) -> str:
    year = int(period[:4])
    month = int(period[5:7])
    quarter = ((month - 1) // 3) + 1
    return f"{year:04d}-Q{quarter}"


def _parse_months(params: dict[str, Any]) -> list[str] | None:
    raw_months = params.get("months")
    if raw_months is None:
        return None
    months: list[str] = []
    for value in str(raw_months).split(","):
        month = value.strip()
        if not month:
            continue
        if len(month) != 7 or month[4] != "-":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="months entries must use YYYY-MM format",
            )
        year = int(month[:4])
        mon = int(month[5:7])
        if year < 1900 or mon < 1 or mon > 12:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="months entries must use YYYY-MM format",
            )
        months.append(f"{year:04d}-{mon:02d}")
    if not months:
        return None
    return sorted(set(months))


def _normalize_query(params: dict[str, Any]) -> str:
    query_pairs: list[tuple[str, str]] = []
    for key in sorted(params):
        value = params[key]
        if value is None:
            continue
        if isinstance(value, bool):
            query_pairs.append((key, "true" if value else "false"))
            continue
        if isinstance(value, list):
            query_pairs.append((key, ",".join(str(item) for item in value)))
            continue
        query_pairs.append((key, str(value)))
    return urlencode(query_pairs)


def _fetch_ledger_rows(*, date_from: str, date_to: str, include_void: bool) -> list[dict[str, Any]]:
    conditions = ["t.date >= ?", "t.date <= ?"]
    query_params: list[Any] = [date_from, date_to]
    if not include_void:
        conditions.append("t.status = 'posted'")
    where_sql = " AND ".join(conditions)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT t.id AS transaction_id, t.date, t.status, tl.account_id, tl.direction,
                   tl.amount_cents, tl.category_id, a.code AS account_code, a.name AS account_name,
                   a.type AS account_type, c.name AS category_name
            FROM transaction_lines tl
            JOIN transactions t ON t.id = tl.transaction_id
            JOIN accounts a ON a.id = tl.account_id
            LEFT JOIN categories c ON c.id = tl.category_id
            WHERE {where_sql}
            ORDER BY t.date ASC, t.id ASC, tl.id ASC
            """,
            tuple(query_params),
        ).fetchall()
    return [dict(row) for row in rows]


def _run_coa_report(params: dict[str, Any]) -> dict[str, Any]:
    as_of = str(params.get("as_of") or _today().isoformat())
    _parse_iso_date(as_of, field="as_of")
    include_void = _parse_bool(params.get("include_void"), default=False)
    rows = _fetch_ledger_rows(date_from="1900-01-01", date_to=as_of, include_void=include_void)
    balances_by_account: dict[int, int] = defaultdict(int)
    for row in rows:
        account_type = str(row["account_type"])
        if account_type not in ACCOUNT_TYPES:
            continue
        balances_by_account[int(row["account_id"])] += _signed_for_account_type(
            account_type=account_type,
            direction=str(row["direction"]),
            amount_cents=int(row["amount_cents"]),
        )

    with connect() as conn:
        accounts = conn.execute(
            """
            SELECT id, code, name, type, subtype, is_archived
            FROM accounts
            ORDER BY type ASC, code ASC, id ASC
            """
        ).fetchall()

    result_rows: list[dict[str, Any]] = []
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    subtotals: dict[str, int] = defaultdict(int)
    for account in accounts:
        account_id = int(account["id"])
        balance_cents = int(balances_by_account.get(account_id, 0))
        serialized = {
            "account_id": account_id,
            "code": account["code"],
            "name": account["name"],
            "type": account["type"],
            "subtype": account["subtype"],
            "is_archived": bool(int(account["is_archived"] or 0)),
            "balance_cents": balance_cents,
        }
        result_rows.append(serialized)
        grouped[str(account["type"])].append(serialized)
        subtotals[str(account["type"])] += balance_cents

    normalized_params = {"as_of": as_of, "include_void": include_void}
    return {
        "kind": "coa",
        "params": normalized_params,
        "query": _normalize_query(normalized_params),
        "headers": ["code", "name", "type", "subtype", "is_archived", "balance_cents"],
        "rows": result_rows,
        "groups": [
            {"type": account_type, "subtotal_cents": int(subtotals.get(account_type, 0))}
            for account_type in sorted(grouped)
        ],
        "totals": {
            "asset_cents": int(subtotals.get("asset", 0)),
            "liability_cents": int(subtotals.get("liability", 0)),
            "equity_cents": int(subtotals.get("equity", 0)),
            "income_cents": int(subtotals.get("income", 0)),
            "expense_cents": int(subtotals.get("expense", 0)),
            "balance_sheet_delta_cents": int(subtotals.get("asset", 0))
            - (int(subtotals.get("liability", 0)) + int(subtotals.get("equity", 0))),
        },
    }


def _group_by_category(entries: dict[str, int]) -> list[dict[str, Any]]:
    return [
        {"category_name": category_name, "amount_cents": amount_cents}
        for category_name, amount_cents in sorted(
            entries.items(),
            key=lambda item: (-item[1], item[0].lower()),
        )
    ]


def _run_summary_report(params: dict[str, Any]) -> dict[str, Any]:
    report_range = _parse_range_params(params)
    include_void = _parse_bool(params.get("include_void"), default=False)
    rows = _fetch_ledger_rows(
        date_from=report_range.date_from,
        date_to=report_range.date_to,
        include_void=include_void,
    )

    income_accounts: dict[str, int] = defaultdict(int)
    expense_accounts: dict[str, int] = defaultdict(int)
    income_categories: dict[str, int] = defaultdict(int)
    expense_categories: dict[str, int] = defaultdict(int)

    for row in rows:
        account_type = str(row["account_type"])
        if account_type not in {"income", "expense"}:
            continue
        amount_cents = _income_expense_contribution(
            account_type=account_type,
            direction=str(row["direction"]),
            amount_cents=int(row["amount_cents"]),
        )
        account_label = f"{row['account_code']} · {row['account_name']}"
        category_name = str(row["category_name"] or "(uncategorized)")
        if account_type == "income":
            income_accounts[account_label] += amount_cents
            income_categories[category_name] += amount_cents
        else:
            expense_accounts[account_label] += amount_cents
            expense_categories[category_name] += amount_cents

    income_rows = [
        {"account": account, "amount_cents": amount}
        for account, amount in sorted(income_accounts.items(), key=lambda item: (-item[1], item[0]))
    ]
    expense_rows = [
        {"account": account, "amount_cents": amount}
        for account, amount in sorted(
            expense_accounts.items(), key=lambda item: (-item[1], item[0])
        )
    ]
    income_total = sum(income_accounts.values())
    expense_total = sum(expense_accounts.values())

    normalized_params = {
        "date_from": report_range.date_from,
        "date_to": report_range.date_to,
        "include_void": include_void,
    }
    return {
        "kind": "summary",
        "params": normalized_params,
        "query": _normalize_query(normalized_params),
        "headers": ["account", "amount_cents"],
        "rows": {
            "income": income_rows,
            "expense": expense_rows,
        },
        "income_categories": _group_by_category(income_categories),
        "expense_categories": _group_by_category(expense_categories),
        "totals": {
            "income_cents": income_total,
            "expense_cents": expense_total,
            "surplus_cents": income_total - expense_total,
        },
    }


def _raw_monthly_income_by_lines(
    *,
    date_from: str,
    date_to: str,
    include_void: bool,
) -> dict[str, int]:
    conditions = ["t.date >= ?", "t.date <= ?", "a.type = 'income'", "tl.direction = 'credit'"]
    query_params: list[Any] = [date_from, date_to]
    if not include_void:
        conditions.append("t.status = 'posted'")
    where_sql = " AND ".join(conditions)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT substr(t.date, 1, 7) AS month, SUM(tl.amount_cents) AS income_cents
            FROM transaction_lines tl
            JOIN transactions t ON t.id = tl.transaction_id
            JOIN accounts a ON a.id = tl.account_id
            WHERE {where_sql}
            GROUP BY substr(t.date, 1, 7)
            """,
            tuple(query_params),
        ).fetchall()
    return {str(row["month"]): int(row["income_cents"] or 0) for row in rows}


def _run_monthly_report(params: dict[str, Any]) -> dict[str, Any]:
    report_range = _parse_range_params(params)
    include_void = _parse_bool(params.get("include_void"), default=False)
    include_accounts = _parse_bool(params.get("include_accounts"), default=False)
    selected_months = _parse_months(params)
    all_periods = _month_periods(report_range.date_from, report_range.date_to)
    periods = selected_months if selected_months is not None else all_periods

    monthly: dict[str, dict[str, Any]] = {
        period: {
            "period": period,
            "income_cents": 0,
            "expense_cents": 0,
            "top_expense_categories": defaultdict(int),
            "accounts": defaultdict(int),
        }
        for period in periods
    }

    rows = _fetch_ledger_rows(
        date_from=report_range.date_from,
        date_to=report_range.date_to,
        include_void=include_void,
    )
    for row in rows:
        period = str(row["date"])[:7]
        if period not in monthly:
            continue
        account_type = str(row["account_type"])
        if account_type not in {"income", "expense"}:
            continue
        contribution = _income_expense_contribution(
            account_type=account_type,
            direction=str(row["direction"]),
            amount_cents=int(row["amount_cents"]),
        )
        if account_type == "income":
            monthly[period]["income_cents"] += contribution
        else:
            monthly[period]["expense_cents"] += contribution
            category_name = str(row["category_name"] or "(uncategorized)")
            monthly[period]["top_expense_categories"][category_name] += contribution
        if include_accounts:
            account_name = f"{row['account_code']} · {row['account_name']}"
            monthly[period]["accounts"][account_name] += contribution

    result_rows: list[dict[str, Any]] = []
    for period in periods:
        item = monthly[period]
        top_categories = _group_by_category(item["top_expense_categories"])[:5]
        row = {
            "period": period,
            "income_cents": int(item["income_cents"]),
            "expense_cents": int(item["expense_cents"]),
            "net_cents": int(item["income_cents"]) - int(item["expense_cents"]),
            "top_expense_categories": top_categories,
        }
        if include_accounts:
            row["accounts"] = [
                {"account": name, "amount_cents": amount}
                for name, amount in sorted(
                    item["accounts"].items(),
                    key=lambda account_row: (-account_row[1], account_row[0]),
                )
            ]
        result_rows.append(row)

    totals = {
        "income_cents": sum(int(item["income_cents"]) for item in result_rows),
        "expense_cents": sum(int(item["expense_cents"]) for item in result_rows),
    }
    totals["net_cents"] = totals["income_cents"] - totals["expense_cents"]

    raw_income = _raw_monthly_income_by_lines(
        date_from=report_range.date_from,
        date_to=report_range.date_to,
        include_void=include_void,
    )
    report_income = {item["period"]: int(item["income_cents"]) for item in result_rows}
    integrity = {
        "raw_income_by_period": raw_income,
        "matches": all(
            report_income.get(period, 0) == raw_income.get(period, 0) for period in periods
        ),
    }

    normalized_params = {
        "date_from": report_range.date_from,
        "date_to": report_range.date_to,
        "months": periods if selected_months is not None else None,
        "include_void": include_void,
        "include_accounts": include_accounts,
    }
    return {
        "kind": "monthly",
        "params": {key: value for key, value in normalized_params.items() if value is not None},
        "query": _normalize_query(normalized_params),
        "headers": ["period", "income_cents", "expense_cents", "net_cents"],
        "rows": result_rows,
        "totals": totals,
        "integrity": integrity,
    }


def _run_quarterly_report(params: dict[str, Any]) -> dict[str, Any]:
    include_void = _parse_bool(params.get("include_void"), default=False)
    include_accounts = _parse_bool(params.get("include_accounts"), default=False)
    year = params.get("year")
    if year is not None:
        report_year = int(year)
        report_range = ReportRange(
            date_from=f"{report_year:04d}-01-01",
            date_to=f"{report_year:04d}-12-31",
        )
    else:
        report_range = _parse_range_params(params)
        report_year = None

    months = _month_periods(report_range.date_from, report_range.date_to)
    quarter_periods = sorted({_quarter_from_month(month) for month in months})
    quarterly: dict[str, dict[str, Any]] = {
        period: {
            "period": period,
            "income_cents": 0,
            "expense_cents": 0,
            "top_expense_categories": defaultdict(int),
            "accounts": defaultdict(int),
        }
        for period in quarter_periods
    }

    rows = _fetch_ledger_rows(
        date_from=report_range.date_from,
        date_to=report_range.date_to,
        include_void=include_void,
    )
    for row in rows:
        quarter = _quarter_from_month(str(row["date"])[:7])
        if quarter not in quarterly:
            continue
        account_type = str(row["account_type"])
        if account_type not in {"income", "expense"}:
            continue
        contribution = _income_expense_contribution(
            account_type=account_type,
            direction=str(row["direction"]),
            amount_cents=int(row["amount_cents"]),
        )
        if account_type == "income":
            quarterly[quarter]["income_cents"] += contribution
        else:
            quarterly[quarter]["expense_cents"] += contribution
            category_name = str(row["category_name"] or "(uncategorized)")
            quarterly[quarter]["top_expense_categories"][category_name] += contribution
        if include_accounts:
            account_name = f"{row['account_code']} · {row['account_name']}"
            quarterly[quarter]["accounts"][account_name] += contribution

    result_rows: list[dict[str, Any]] = []
    for period in quarter_periods:
        item = quarterly[period]
        row = {
            "period": period,
            "income_cents": int(item["income_cents"]),
            "expense_cents": int(item["expense_cents"]),
            "net_cents": int(item["income_cents"]) - int(item["expense_cents"]),
            "top_expense_categories": _group_by_category(item["top_expense_categories"])[:5],
        }
        if include_accounts:
            row["accounts"] = [
                {"account": name, "amount_cents": amount}
                for name, amount in sorted(
                    item["accounts"].items(),
                    key=lambda account_row: (-account_row[1], account_row[0]),
                )
            ]
        result_rows.append(row)

    totals = {
        "income_cents": sum(int(item["income_cents"]) for item in result_rows),
        "expense_cents": sum(int(item["expense_cents"]) for item in result_rows),
    }
    totals["net_cents"] = totals["income_cents"] - totals["expense_cents"]

    normalized_params: dict[str, Any] = {
        "date_from": report_range.date_from,
        "date_to": report_range.date_to,
        "include_void": include_void,
        "include_accounts": include_accounts,
        "year": report_year,
    }
    return {
        "kind": "quarterly",
        "params": {key: value for key, value in normalized_params.items() if value is not None},
        "query": _normalize_query(normalized_params),
        "headers": ["period", "income_cents", "expense_cents", "net_cents"],
        "rows": result_rows,
        "totals": totals,
    }


def _ensure_report_valuation_tables() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY,
                account_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                quantity_q4 INTEGER NOT NULL,
                avg_cost_q4 INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                realized_gain_loss_cents INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS price_cache (
                id INTEGER PRIMARY KEY,
                ticker TEXT NOT NULL,
                date TEXT NOT NULL,
                close_q4 INTEGER NOT NULL,
                volume INTEGER NOT NULL DEFAULT 0,
                source TEXT NOT NULL DEFAULT 'manual',
                fetched_at INTEGER NOT NULL,
                UNIQUE(ticker, date)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS latest_quotes (
                ticker TEXT PRIMARY KEY,
                price_q4 INTEGER NOT NULL,
                asof TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'manual',
                fetched_at INTEGER NOT NULL
            )
            """
        )
        conn.commit()


def _net_liquid_accounts() -> list[tuple[int, str, int]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                a.id,
                a.type,
                a.subtype,
                COALESCE(
                    SUM(
                        CASE
                            WHEN tl.direction = 'debit' THEN tl.amount_cents
                            WHEN tl.direction = 'credit' THEN -tl.amount_cents
                            ELSE 0
                        END
                    ),
                    0
                ) AS balance_cents
            FROM accounts a
            LEFT JOIN transaction_lines tl ON tl.account_id = a.id
            LEFT JOIN transactions t ON t.id = tl.transaction_id AND t.status = 'posted'
            WHERE a.type IN ('asset', 'liability')
              AND a.subtype IN ('cash', 'bank', 'credit_card', 'other')
            GROUP BY a.id, a.type, a.subtype
            """
        ).fetchall()
    balances: list[tuple[int, str, int]] = []
    for row in rows:
        account_type = str(row["type"])
        amount = int(row["balance_cents"] or 0)
        if account_type == "asset":
            balances.append((int(row["id"]), account_type, amount))
        else:
            balances.append((int(row["id"]), account_type, -amount))
    return balances


def _balance_by_account_up_to(as_of: str, include_void: bool) -> dict[int, int]:
    rows = _fetch_ledger_rows(date_from="1900-01-01", date_to=as_of, include_void=include_void)
    balances: dict[int, int] = defaultdict(int)
    for row in rows:
        account_id = int(row["account_id"])
        account_type = str(row["account_type"])
        if account_type not in ACCOUNT_TYPES:
            continue
        balances[account_id] += _signed_for_account_type(
            account_type=account_type,
            direction=str(row["direction"]),
            amount_cents=int(row["amount_cents"]),
        )
    return balances


def _account_rows_for_date(as_of: str) -> dict[int, dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, code, name, type, subtype, is_archived FROM accounts ORDER BY id ASC"
        ).fetchall()
    return {int(row["id"]): dict(row) for row in rows}


def _resolve_quote_price(ticker: str, as_of: str) -> int:
    with connect() as conn:
        latest = conn.execute(
            """
            SELECT price_q4, asof
            FROM latest_quotes
            WHERE ticker = ? AND asof <= ?
            ORDER BY asof DESC, fetched_at DESC
            LIMIT 1
            """,
            (ticker.upper(), as_of),
        ).fetchone()
        if latest is not None:
            return int(latest["price_q4"])
        cached = conn.execute(
            """
            SELECT close_q4, date
            FROM price_cache
            WHERE ticker = ? AND date <= ?
            ORDER BY date DESC, fetched_at DESC
            LIMIT 1
            """,
            (ticker.upper(), as_of),
        ).fetchone()
        if cached is not None:
            return int(cached["close_q4"])
    return 0


def _position_market_value_for_date(as_of: str) -> dict[str, int]:
    _ensure_report_valuation_tables()
    with connect() as conn:
        rows = conn.execute(
            "SELECT account_id, ticker, quantity_q4 FROM positions WHERE status = 'open'"
        ).fetchall()
    values: dict[str, int] = defaultdict(int)
    for row in rows:
        ticker = str(row["ticker"]).upper()
        quantity_q4 = int(row["quantity_q4"])
        price_q4 = _resolve_quote_price(ticker, as_of)
        if price_q4 <= 0:
            continue
        values[ticker] += (quantity_q4 * price_q4) // 1_000_000
    return values


def _liquid_balance_at_date(as_of: str, *, include_void: bool = False) -> int:
    balances = _balance_by_account_up_to(as_of, include_void=include_void)
    accounts = _account_rows_for_date(as_of)
    total = 0
    for account_id, balance in balances.items():
        account = accounts.get(account_id)
        if account is None:
            continue
        account_type = str(account.get("type") or "")
        subtype = str(account.get("subtype") or "")
        if account_type == "asset" and subtype in {"cash", "bank"}:
            total += balance
        elif account_type == "liability":
            total -= balance
    return total


def _report_periods(date_from: str, date_to: str) -> list[str]:
    start = _parse_iso_date(date_from, field="date_from")
    end = _parse_iso_date(date_to, field="date_to")
    delta_days = (end - start).days
    if delta_days <= 62:
        cursor = start
        points: list[str] = []
        while cursor <= end:
            points.append(cursor.isoformat())
            cursor += timedelta(days=1)
        return points

    periods: list[str] = []
    cursor = date(start.year, start.month, 1)
    stop = date(end.year, end.month, 1)
    while cursor <= stop:
        last_day = monthrange(cursor.year, cursor.month)[1]
        periods.append(date(cursor.year, cursor.month, last_day).isoformat())
        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)
    return periods


def _run_cash_flow_report(params: dict[str, Any]) -> dict[str, Any]:
    report_range = _parse_range_params(params)
    include_void = _parse_bool(params.get("include_void"), default=False)
    opening = _liquid_balance_at_date(
        (date.fromisoformat(report_range.date_from) - timedelta(days=1)).isoformat(),
        include_void=include_void,
    )
    rows = _fetch_ledger_rows(
        date_from=report_range.date_from,
        date_to=report_range.date_to,
        include_void=include_void,
    )

    inflow_by_category: dict[str, int] = defaultdict(int)
    outflow_by_category: dict[str, int] = defaultdict(int)
    inflow_total = 0
    outflow_total = 0
    for row in rows:
        account_type = str(row["account_type"])
        account_name = str(row["account_name"])
        category_name = str(row["category_name"] or "(uncategorized)")
        if account_type == "income":
            amount = (
                int(row["amount_cents"])
                if str(row["direction"]) == "credit"
                else -int(row["amount_cents"])
            )
            if amount > 0:
                inflow_by_category[category_name or account_name] += amount
                inflow_total += amount
        elif account_type == "expense":
            amount = (
                int(row["amount_cents"])
                if str(row["direction"]) == "debit"
                else -int(row["amount_cents"])
            )
            if amount > 0:
                outflow_by_category[category_name or account_name] += amount
                outflow_total += amount

    rows_out = [
        {"category": category, "amount_cents": amount, "kind": "inflow"}
        for category, amount in sorted(
            inflow_by_category.items(), key=lambda item: (-item[1], item[0])
        )
    ] + [
        {"category": category, "amount_cents": amount, "kind": "outflow"}
        for category, amount in sorted(
            outflow_by_category.items(), key=lambda item: (-item[1], item[0])
        )
    ]
    closing = opening + inflow_total - outflow_total
    normalized_params = {
        "date_from": report_range.date_from,
        "date_to": report_range.date_to,
        "include_void": include_void,
    }
    return {
        "kind": "cash_flow",
        "params": normalized_params,
        "query": _normalize_query(normalized_params),
        "headers": ["kind", "category", "amount_cents"],
        "rows": rows_out,
        "totals": {
            "opening_net_liquid_cents": opening,
            "inflow_cents": inflow_total,
            "outflow_cents": outflow_total,
            "closing_net_liquid_cents": closing,
        },
    }


def _run_net_worth_report(params: dict[str, Any]) -> dict[str, Any]:
    report_range = _parse_range_params(params)
    include_void = _parse_bool(params.get("include_void"), default=False)
    periods = _report_periods(report_range.date_from, report_range.date_to)
    rows: list[dict[str, Any]] = []
    for marker in periods:
        as_of = marker
        balances = _balance_by_account_up_to(as_of, include_void=include_void)
        accounts = _account_rows_for_date(as_of)
        asset_value = 0
        liability_value = 0
        for account_id, balance in balances.items():
            account = accounts.get(account_id)
            if account is None:
                continue
            if str(account.get("type") or "") == "asset":
                asset_value += balance
            elif str(account.get("type") or "") == "liability":
                liability_value += balance
        holdings_value = sum(_position_market_value_for_date(as_of).values())
        net_worth = asset_value + holdings_value - liability_value
        rows.append(
            {
                "period": as_of,
                "asset_value_cents": asset_value,
                "liability_value_cents": liability_value,
                "holdings_value_cents": holdings_value,
                "net_worth_cents": net_worth,
            }
        )
    totals = rows[-1] if rows else {
        "asset_value_cents": 0,
        "liability_value_cents": 0,
        "holdings_value_cents": 0,
        "net_worth_cents": 0,
    }
    normalized_params = {
        "date_from": report_range.date_from,
        "date_to": report_range.date_to,
        "include_void": include_void,
    }
    return {
        "kind": "net_worth",
        "params": normalized_params,
        "query": _normalize_query(normalized_params),
        "headers": [
            "period",
            "asset_value_cents",
            "liability_value_cents",
            "holdings_value_cents",
            "net_worth_cents",
        ],
        "rows": rows,
        "totals": {
            "asset_value_cents": int(totals["asset_value_cents"]),
            "liability_value_cents": int(totals["liability_value_cents"]),
            "holdings_value_cents": int(totals["holdings_value_cents"]),
            "net_worth_cents": int(totals["net_worth_cents"]),
        },
    }


def _report_export_filename(kind: str, *, date_from: str, date_to: str, file_format: str) -> str:
    sanitized_kind = kind.strip().lower().replace("_", "-")
    return f"investflow-{sanitized_kind}-{date_from}-{date_to}.{file_format.lower()}"


def _xlsx_serialize(rows: list[dict[str, Any]], headers: list[str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as workbook:
        workbook.writestr(
            "[Content_Types].xml",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
                '  <Default Extension="rels" '
                'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
                '  <Default Extension="xml" ContentType="application/xml"/>\n'
                '  <Override PartName="/xl/workbook.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.'
                'spreadsheetml.sheet.main+xml"/>\n'
                '  <Override PartName="/xl/worksheets/sheet1.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.'
                'spreadsheetml.worksheet+xml"/>\n'
                '  <Override PartName="/docProps/core.xml" '
                'ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>\n'
                '  <Override PartName="/docProps/app.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.'
                'extended-properties+xml"/>\n'
                '</Types>\n'
            ),
        )
        workbook.writestr(
            "_rels/.rels",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<Relationships '
                'xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
                '  <Relationship Id="rId1" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                'relationships/officeDocument" Target="xl/workbook.xml"/>\n'
                '  <Relationship Id="rId2" '
                'Type="http://schemas.openxmlformats.org/package/2006/relationships/'
                'metadata/core-properties" Target="docProps/core.xml"/>\n'
                '  <Relationship Id="rId3" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                'relationships/extended-properties" Target="docProps/app.xml"/>\n'
                '</Relationships>\n'
            ),
        )
        workbook.writestr(
            "docProps/core.xml",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<cp:coreProperties '
                'xmlns:cp="http://schemas.openxmlformats.org/package/2006/'
                'metadata/core-properties" '
                'xmlns:dc="http://purl.org/dc/elements/1.1/" '
                'xmlns:dcterms="http://purl.org/dc/terms/" '
                'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
                'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
                '  <dc:creator>InvestFlow</dc:creator>\n'
                '  <cp:lastModifiedBy>InvestFlow</cp:lastModifiedBy>\n'
                '</cp:coreProperties>\n'
            ),
        )
        workbook.writestr(
            "docProps/app.xml",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<Properties '
                'xmlns="http://schemas.openxmlformats.org/officeDocument/2006/'
                'extended-properties" '
                'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/'
                'docPropsVTypes">\n'
                '  <Application>InvestFlow</Application>\n'
                '</Properties>\n'
            ),
        )
        workbook.writestr(
            "xl/workbook.xml",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<workbook '
                'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/'
                'relationships">\n'
                '  <sheets>\n'
                '    <sheet name="Report" sheetId="1" r:id="rId1"/>\n'
                '  </sheets>\n'
                '</workbook>\n'
            ),
        )
        workbook.writestr(
            "xl/_rels/workbook.xml.rels",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<Relationships '
                'xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
                '  <Relationship Id="rId1" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                'relationships/worksheet" Target="worksheets/sheet1.xml"/>\n'
                '</Relationships>\n'
            ),
        )

        def cell_xml(value: object, column_index: int, row_index: int) -> str:
            cell_ref = f"{chr(65 + (column_index % 26))}{row_index + 1}"
            if isinstance(value, (int, float)):
                return f'<c r="{cell_ref}" t="n"><v>{value}</v></c>'
            escaped = (
                str(value)
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )
            return f'<c r="{cell_ref}" t="inlineStr"><is><t>{escaped}</t></is></c>'

        sheet_rows: list[str] = []
        header_row = "<row r='1'>" + "".join(
            cell_xml(header, idx, 0) for idx, header in enumerate(headers)
        ) + "</row>"
        sheet_rows.append(header_row)
        for row_index, entry in enumerate(rows, start=1):
            values = [entry.get(header, "") for header in headers]
            sheet_rows.append(
                f"<row r='{row_index + 1}'>"
                + "".join(cell_xml(value, idx, row_index) for idx, value in enumerate(values))
                + "</row>"
            )
        workbook.writestr(
            "xl/worksheets/sheet1.xml",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">\n'
                '  <sheetViews><sheetView workbookViewId="0"/></sheetViews>\n'
                '  <sheetData>\n'
                '    {rows}\n'
                '  </sheetData>\n'
                '</worksheet>\n'
            ).format(rows="".join(sheet_rows)),
        )

    return buffer.getvalue()


def _pdf_serialize(report: dict[str, Any]) -> bytes:
    lines = [
        f"InvestFlow {report['kind']} report",
        (
            "range: "
            f"{report.get('params', {}).get('date_from')} -> "
            f"{report.get('params', {}).get('date_to')}"
        ),
    ]
    for key, value in sorted(report.get("totals", {}).items()):
        lines.append(f"{key}: {value}")
    for row in report.get("rows", [])[:20]:
        lines.append(str(row))
    text_body = "\n".join(lines)
    escaped = text_body.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    objects: list[str] = []
    objects.append("<< /Type /Catalog /Pages 2 0 R >>")
    objects.append("<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    objects.append(
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>"
    )
    stream = f"BT /F1 12 Tf 50 760 Td ({escaped}) Tj ET"
    objects.append(f"<< /Length {len(stream.encode('latin-1'))} >>\nstream\n{stream}\nendstream")
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    content: list[bytes] = [b"%PDF-1.4\n"]
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(b"".join(content)))
        content.append(f"{index} 0 obj\n{obj}\nendobj\n".encode("latin-1"))
    xref_pos = len(b"".join(content))
    content.append(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for offset in offsets[1:]:
        content.append(f"{offset:010d} 00000 n \n".encode("latin-1"))
    content.append(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_pos}\n%%EOF\n"
        ).encode("latin-1")
    )
    return b"".join(content)


def export_report(
    kind: str,
    params: dict[str, Any],
    file_format: str = "xlsx",
) -> tuple[bytes, str]:
    normalized_kind = kind.strip().lower()
    report = run_report(normalized_kind, params)
    file_ext = str(file_format or "xlsx").strip().lower()
    filename = _report_export_filename(
        normalized_kind,
        date_from=str(report["params"].get("date_from", "")),
        date_to=str(report["params"].get("date_to", "")),
        file_format=file_ext,
    )
    if file_ext == "pdf":
        return _pdf_serialize(report), filename
    return _xlsx_serialize(report.get("rows", []), report.get("headers", [])), filename


def build_report_xlsx(kind: str, params: dict[str, Any]) -> tuple[bytes, str]:
    return export_report(kind, params, "xlsx")


def build_report_pdf(kind: str, params: dict[str, Any]) -> tuple[bytes, str]:
    return export_report(kind, params, "pdf")


def run_report(kind: str, params: dict[str, Any]) -> dict[str, Any]:
    ensure_seeded_coa()
    ensure_seeded_categories()
    ensure_transactions_tables()

    normalized_kind = kind.strip().lower()
    if normalized_kind not in REPORT_KINDS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown report kind")
    if normalized_kind == "coa":
        return _run_coa_report(params)
    if normalized_kind == "summary":
        return _run_summary_report(params)
    if normalized_kind == "monthly":
        return _run_monthly_report(params)
    if normalized_kind == "quarterly":
        return _run_quarterly_report(params)
    if normalized_kind == "cash_flow":
        return _run_cash_flow_report(params)
    if normalized_kind == "net_worth":
        return _run_net_worth_report(params)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown report kind")
