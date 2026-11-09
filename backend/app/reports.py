from __future__ import annotations

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

REPORT_KINDS = {"coa", "summary", "monthly", "quarterly"}
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


def _parse_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
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
    return _run_quarterly_report(params)
