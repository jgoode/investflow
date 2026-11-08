from __future__ import annotations

import sqlite3
import time
from collections.abc import Sequence
from datetime import date, timedelta
from typing import Any

from fastapi import HTTPException, status

from app.categories import ensure_seeded_categories
from app.crypto_store import mask_account_sensitive, read_account_sensitive
from app.db.connection import connect


def _now_ts() -> int:
    return int(time.time())


def _today_iso() -> str:
    return date.today().isoformat()


def _fetch_account(account_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT id, code, name, type, subtype, is_archived, parent_id "
            "FROM accounts WHERE id = ?",
            (account_id,),
        ).fetchone()
    return dict(row) if row is not None else None


def _fetch_category(category_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT id, name, flow, default_account_id FROM categories WHERE id = ?",
            (category_id,),
        ).fetchone()
    return dict(row) if row is not None else None


def _ensure_leaf_account(account_id: int) -> dict[str, Any]:
    account = _fetch_account(account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="account not found")
    if bool(int(account.get("is_archived") or 0)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="account is archived",
        )
    if str(account.get("subtype") or "").lower() == "group":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="group accounts are not valid posting targets",
        )
    return account


def ensure_transactions_tables() -> None:
    ensure_seeded_categories()
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY,
                date TEXT NOT NULL,
                description TEXT NOT NULL,
                reference TEXT NULL,
                status TEXT NOT NULL CHECK(status IN ('posted', 'void')) DEFAULT 'posted',
                created_by INTEGER NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE SET NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS transaction_lines (
                id INTEGER PRIMARY KEY,
                transaction_id INTEGER NOT NULL,
                account_id INTEGER NOT NULL,
                direction TEXT NOT NULL CHECK(direction IN ('debit', 'credit')),
                amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
                memo TEXT NULL,
                category_id INTEGER NULL,
                FOREIGN KEY(transaction_id) REFERENCES transactions(id) ON DELETE CASCADE,
                FOREIGN KEY(account_id) REFERENCES accounts(id),
                FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE SET NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS ix_transactions_date ON transactions(date)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_transaction_lines_account_id "
            "ON transaction_lines(account_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_transaction_lines_category_id "
            "ON transaction_lines(category_id)"
        )
        conn.commit()


def _line_mask(account_id: int) -> str:
    if account_id <= 0:
        return "•••"
    sensitive = read_account_sensitive(account_id)
    value = sensitive.get("account_number_enc")
    return mask_account_sensitive(value, "account_number_enc")


def _serialize_line(row: sqlite3.Row) -> dict[str, Any]:
    amount = int(row["amount_cents"])
    account_id = int(row["account_id"])
    category_id = row["category_id"]
    memo = row["memo"]
    return {
        "id": int(row["line_id"]),
        "account_id": account_id,
        "account_name": row["account_name"],
        "account_type": row["account_type"],
        "account_number_mask": _line_mask(account_id),
        "direction": row["direction"],
        "amount_cents": amount,
        "memo": memo,
        "category_id": int(category_id) if category_id is not None else None,
        "category_name": row["category_name"],
    }


def _serialize_transaction(tx_row: sqlite3.Row, lines: Sequence[sqlite3.Row]) -> dict[str, Any]:
    return {
        "id": int(tx_row["id"]),
        "date": tx_row["date"],
        "description": tx_row["description"],
        "reference": tx_row["reference"],
        "status": tx_row["status"],
        "created_by": tx_row["created_by"],
        "created_at": int(tx_row["created_at"]),
        "updated_at": int(tx_row["updated_at"]),
        "lines": [_serialize_line(line) for line in lines],
    }


def _parse_date(value: str | None, *, default_days_ago: int = 90) -> tuple[str, str]:
    if value:
        try:
            return value, value
        except Exception as exc:  # pragma: no cover - defensive
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="invalid date",
            ) from exc
    start = (date.today() - timedelta(days=default_days_ago)).isoformat()
    end = _today_iso()
    return start, end


def _build_quick_lines(payload: dict[str, Any]) -> list[dict[str, Any]]:
    mode = str(payload.get("mode") or "").strip().lower()
    account_id = payload.get("account_id")
    category_id = payload.get("category_id")
    amount_cents = payload.get("amount_cents")
    if mode not in {"income", "expense"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="quick-post mode must be income or expense",
        )
    if account_id is None or category_id is None or amount_cents is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="quick-post requires account_id, category_id, and amount_cents",
        )

    category = _fetch_category(int(category_id))
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="category not found")
    if category["flow"] != mode:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="category flow does not match posting mode",
        )

    target_account_id = category.get("default_account_id")
    if target_account_id is None:
        user_target = payload.get("target_account_id") or payload.get("account_target_id")
        if user_target is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="category default account not configured",
            )
        target_account_id = int(user_target)
    target_account_id = int(target_account_id)
    _ensure_leaf_account(int(account_id))
    _ensure_leaf_account(target_account_id)

    if mode == "expense":
        return [
            {
                "account_id": target_account_id,
                "direction": "debit",
                "amount_cents": int(amount_cents),
                "memo": payload.get("memo"),
                "category_id": int(category_id),
            },
            {
                "account_id": int(account_id),
                "direction": "credit",
                "amount_cents": int(amount_cents),
                "memo": payload.get("memo"),
                "category_id": int(category_id),
            },
        ]
    return [
        {
            "account_id": int(account_id),
            "direction": "debit",
            "amount_cents": int(amount_cents),
            "memo": payload.get("memo"),
            "category_id": int(category_id),
        },
        {
            "account_id": target_account_id,
            "direction": "credit",
            "amount_cents": int(amount_cents),
            "memo": payload.get("memo"),
            "category_id": int(category_id),
        },
    ]


def _normalize_line(raw_line: dict[str, Any]) -> dict[str, Any]:
    account_id = raw_line.get("account_id")
    direction = str(raw_line.get("direction") or "").strip().lower()
    amount_cents = raw_line.get("amount_cents")
    if account_id is None or direction not in {"debit", "credit"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="every line needs account_id, direction, and amount_cents",
        )
    if amount_cents is None or int(amount_cents) <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="amount_cents must be a positive integer",
        )
    _ensure_leaf_account(int(account_id))
    category_id = raw_line.get("category_id")
    if category_id is not None:
        category = _fetch_category(int(category_id))
        if category is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="category not found")
    return {
        "account_id": int(account_id),
        "direction": direction,
        "amount_cents": int(amount_cents),
        "memo": raw_line.get("memo"),
        "category_id": int(category_id) if category_id is not None else None,
    }


def create_transaction(payload: dict[str, Any], *, created_by: int | None = None) -> dict[str, Any]:
    ensure_transactions_tables()
    date_value = str(payload.get("date") or _today_iso()).strip()
    try:
        date.fromisoformat(date_value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="date must use ISO format YYYY-MM-DD",
        ) from exc
    if date_value > _today_iso():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="future-dated posting is not allowed",
        )

    raw_lines = payload.get("lines")
    if not raw_lines:
        raw_lines = _build_quick_lines(payload)
    normalized_lines = [_normalize_line(line) for line in raw_lines]
    if not normalized_lines:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="transaction requires at least one line",
        )

    debits = sum(line["amount_cents"] for line in normalized_lines if line["direction"] == "debit")
    credits = sum(
        line["amount_cents"] for line in normalized_lines if line["direction"] == "credit"
    )
    if debits != credits:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="transaction balance is imbalanced",
        )

    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        tx_cursor = conn.execute(
            """
            INSERT INTO transactions (
                date, description, reference, status, created_by, created_at, updated_at
            )
            VALUES (?, ?, ?, 'posted', ?, ?, ?)
            """,
            (
                date_value,
                str(payload.get("description") or "").strip() or "Transaction",
                payload.get("reference"),
                created_by,
                _now_ts(),
                _now_ts(),
            ),
        )
        last_row_id = tx_cursor.lastrowid
        if last_row_id is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="transaction insertion failed",
            )
        tx_id = int(last_row_id)
        for line in normalized_lines:
            conn.execute(
                """
                INSERT INTO transaction_lines (
                    transaction_id, account_id, direction, amount_cents, memo, category_id
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    tx_id,
                    line["account_id"],
                    line["direction"],
                    line["amount_cents"],
                    line.get("memo"),
                    line.get("category_id"),
                ),
            )
        conn.commit()

    with connect() as conn:
        tx_row = conn.execute(
            "SELECT * FROM transactions WHERE id = ?",
            (tx_id,),
        ).fetchone()
        line_rows = conn.execute(
            """
            SELECT tl.id AS line_id, tl.account_id, tl.direction, tl.amount_cents, tl.memo,
                   tl.category_id, a.name AS account_name, a.type AS account_type,
                   c.name AS category_name
            FROM transaction_lines tl
            LEFT JOIN accounts a ON a.id = tl.account_id
            LEFT JOIN categories c ON c.id = tl.category_id
            WHERE tl.transaction_id = ?
            ORDER BY tl.id ASC
            """,
            (tx_id,),
        ).fetchall()
    return _serialize_transaction(tx_row, line_rows)


def list_transactions(
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    account_id: int | None = None,
    account_type: str | None = None,
    category_id: int | None = None,
    amount_min_cents: int | None = None,
    amount_max_cents: int | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    ensure_transactions_tables()
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20
    if page_size > 50:
        page_size = 50

    default_from = (date.today() - timedelta(days=90)).isoformat()
    default_to = _today_iso()
    start_date = date_from or default_from
    end_date = date_to or default_to

    conditions: list[str] = ["t.date >= ?", "t.date <= ?"]
    params: list[Any] = [start_date, end_date]

    if account_id is not None:
        conditions.append("tl.account_id = ?")
        params.append(int(account_id))
    if account_type:
        conditions.append("a.type = ?")
        params.append(str(account_type).strip().lower())
    if category_id is not None:
        conditions.append("tl.category_id = ?")
        params.append(int(category_id))
    if amount_min_cents is not None:
        conditions.append("tl.amount_cents >= ?")
        params.append(int(amount_min_cents))
    if amount_max_cents is not None:
        conditions.append("tl.amount_cents <= ?")
        params.append(int(amount_max_cents))
    if q:
        needle = f"%{str(q).strip().lower()}%"
        conditions.append(
            "(LOWER(t.description) LIKE ? OR LOWER(COALESCE(t.reference, '')) LIKE ?)"
        )
        params.extend([needle, needle])

    where_sql = " AND ".join(conditions)
    count_sql = (
        "SELECT COUNT(DISTINCT t.id) FROM transactions t "
        "LEFT JOIN transaction_lines tl ON tl.transaction_id = t.id "
        "LEFT JOIN accounts a ON a.id = tl.account_id "
        f"WHERE {where_sql}"
    )

    query_sql = (
        "SELECT t.id AS tx_id, t.date, t.description, t.reference, t.status, "
        "t.created_by, t.created_at, t.updated_at, "
        "tl.id AS line_id, tl.account_id, tl.direction, tl.amount_cents, "
        "tl.memo, tl.category_id, a.name AS account_name, a.type AS account_type, "
        "c.name AS category_name "
        "FROM transactions t "
        "LEFT JOIN transaction_lines tl ON tl.transaction_id = t.id "
        "LEFT JOIN accounts a ON a.id = tl.account_id "
        "LEFT JOIN categories c ON c.id = tl.category_id "
        f"WHERE {where_sql} "
        "ORDER BY t.date DESC, t.id DESC "
        "LIMIT ? OFFSET ?"
    )

    with connect() as conn:
        total = int(conn.execute(count_sql, tuple(params)).fetchone()[0])
        rows = conn.execute(
            query_sql, tuple(params + [page_size, (page - 1) * page_size])
        ).fetchall()

    tx_map: dict[int, dict[str, Any]] = {}
    for row in rows:
        tx_id = int(row["tx_id"])
        if tx_id not in tx_map:
            tx_map[tx_id] = {
                "id": tx_id,
                "date": row["date"],
                "description": row["description"],
                "reference": row["reference"],
                "status": row["status"],
                "created_by": row["created_by"],
                "created_at": int(row["created_at"]),
                "updated_at": int(row["updated_at"]),
                "lines": [],
            }
        if row["line_id"] is not None:
            tx_map[tx_id]["lines"].append(_serialize_line(row))

    transactions = [tx_map[tx_id] for tx_id in sorted(tx_map, reverse=True)]
    return {
        "transactions": transactions,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": max(1, (total + page_size - 1) // page_size) if total else 0,
    }
