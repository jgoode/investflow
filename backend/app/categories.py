from __future__ import annotations

import sqlite3
import time
from collections.abc import Mapping
from typing import Any

from fastapi import HTTPException, status

from app.accounts import ensure_seeded_coa
from app.db.connection import connect

CATEGORY_FLOWS = {"income", "expense"}

SEED_CATEGORIES: list[dict[str, Any]] = [
    {
        "name": "Salary",
        "flow": "income",
        "color": "#2e7d32",
        "default_account_code": "INCOME-SALARY",
    },
    {
        "name": "Interest & Dividends",
        "flow": "income",
        "color": "#1565c0",
        "default_account_code": "INCOME-INTDIV",
    },
    {
        "name": "Realized Gains",
        "flow": "income",
        "color": "#6a1b9a",
        "default_account_code": "INCOME-REALIZED",
    },
    {
        "name": "Other Income",
        "flow": "income",
        "color": "#00897b",
        "default_account_code": "INCOME-OTHER",
    },
    {
        "name": "Housing",
        "flow": "expense",
        "color": "#ef6c00",
        "default_account_code": "EXP-HOUSING",
    },
    {"name": "Food", "flow": "expense", "color": "#f9a825", "default_account_code": "EXP-FOOD"},
    {
        "name": "Transportation",
        "flow": "expense",
        "color": "#8d6e63",
        "default_account_code": "EXP-TRANSPORT",
    },
    {
        "name": "Utilities",
        "flow": "expense",
        "color": "#0277bd",
        "default_account_code": "EXP-UTILITIES",
    },
    {
        "name": "Healthcare",
        "flow": "expense",
        "color": "#c62828",
        "default_account_code": "EXP-HEALTH",
    },
    {
        "name": "Insurance",
        "flow": "expense",
        "color": "#5d4037",
        "default_account_code": "EXP-INSURANCE",
    },
    {
        "name": "Entertainment",
        "flow": "expense",
        "color": "#7b1fa2",
        "default_account_code": "EXP-ENTERTAINMENT",
    },
    {"name": "Travel", "flow": "expense", "color": "#3949ab", "default_account_code": "EXP-TRAVEL"},
    {
        "name": "Education",
        "flow": "expense",
        "color": "#00838f",
        "default_account_code": "EXP-EDUCATION",
    },
    {"name": "Fees", "flow": "expense", "color": "#6d4c41", "default_account_code": "EXP-FEES"},
    {
        "name": "Other Expenses",
        "flow": "expense",
        "color": "#546e7a",
        "default_account_code": "EXP-OTHER",
    },
]


def _now_ts() -> int:
    return int(time.time())


def _serialize_category(row: sqlite3.Row | Mapping[str, Any]) -> dict[str, Any]:
    item = dict(row)
    default_id = item.get("default_account_id")
    item["default_account_id"] = int(default_id) if default_id is not None else None
    return item


def ensure_categories_tables() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                flow TEXT NOT NULL CHECK(flow IN ('income', 'expense')),
                color TEXT NOT NULL DEFAULT '#64748b',
                default_account_id INTEGER NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY(default_account_id) REFERENCES accounts(id) ON DELETE SET NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS ix_categories_flow ON categories(flow)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_categories_default_account_id "
            "ON categories(default_account_id)"
        )
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
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_transaction_lines_transaction_id "
            "ON transaction_lines(transaction_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_transaction_lines_account_id "
            "ON transaction_lines(account_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_transaction_lines_category_id "
            "ON transaction_lines(category_id)"
        )
        conn.commit()


def _fetch_account(account_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT id, type, is_archived FROM accounts WHERE id = ?", (account_id,)
        ).fetchone()
    return dict(row) if row is not None else None


def _default_account_id_for_seed(conn: sqlite3.Connection, account_code: str) -> int | None:
    row = conn.execute("SELECT id FROM accounts WHERE code = ?", (account_code,)).fetchone()
    return int(row["id"]) if row is not None else None


def _validated_flow(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in CATEGORY_FLOWS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="invalid category flow"
        )
    return normalized


def _validate_default_account_for_flow(default_account_id: int | None, flow: str) -> int | None:
    if default_account_id is None:
        return None
    account = _fetch_account(default_account_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="default account not found"
        )
    if str(account["type"]) != flow:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="category flow must match default account type",
        )
    if bool(int(account["is_archived"] or 0)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="default account cannot be archived",
        )
    return default_account_id


def ensure_seeded_categories() -> list[dict[str, Any]]:
    ensure_seeded_coa()
    ensure_categories_tables()
    now = _now_ts()
    with connect() as conn:
        for item in SEED_CATEGORIES:
            default_account_id = _default_account_id_for_seed(conn, item["default_account_code"])
            conn.execute(
                """
                INSERT OR IGNORE INTO categories (
                    name, flow, color, default_account_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    item["name"],
                    item["flow"],
                    item["color"],
                    default_account_id,
                    now,
                    now,
                ),
            )
        conn.execute(
            "INSERT OR REPLACE INTO seed_meta (name, version, applied_at) "
            "VALUES ('categories_v1', 1, ?)",
            (now,),
        )
        conn.commit()
    return _list_categories_raw()


def _list_categories_raw() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM categories ORDER BY flow ASC, name ASC").fetchall()
    return [_serialize_category(row) for row in rows]


def list_categories() -> list[dict[str, Any]]:
    ensure_seeded_categories()
    return _list_categories_raw()


def create_category(payload: Mapping[str, Any]) -> dict[str, Any]:
    name = str(payload.get("name", "")).strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="category name is required"
        )
    flow = _validated_flow(str(payload.get("flow", "")))
    color = str(payload.get("color", "#64748b")).strip() or "#64748b"
    default_account_id_raw = payload.get("default_account_id")
    default_account_id = int(default_account_id_raw) if default_account_id_raw is not None else None
    default_account_id = _validate_default_account_for_flow(default_account_id, flow)
    now = _now_ts()
    with connect() as conn:
        exists = conn.execute("SELECT id FROM categories WHERE name = ?", (name,)).fetchone()
        if exists is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="category name already exists"
            )
        cursor = conn.execute(
            """
            INSERT INTO categories (name, flow, color, default_account_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, flow, color, default_account_id, now, now),
        )
        conn.commit()
        category_id = cursor.lastrowid
    if category_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="category create failed"
        )
    return get_category(int(category_id))


def get_category(category_id: int) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="category not found")
    return _serialize_category(row)


def update_category(category_id: int, payload: Mapping[str, Any]) -> dict[str, Any]:
    existing = get_category(category_id)
    updates: list[str] = []
    values: list[Any] = []
    next_name: str | None = None

    if "name" in payload:
        name = str(payload["name"]).strip()
        if not name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="category name is required",
            )
        next_name = name
        updates.append("name = ?")
        values.append(name)
    next_flow = existing["flow"]
    if "flow" in payload:
        next_flow = _validated_flow(str(payload["flow"]))
        updates.append("flow = ?")
        values.append(next_flow)
    if "color" in payload:
        color = str(payload["color"]).strip()
        if not color:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="category color is required",
            )
        updates.append("color = ?")
        values.append(color)
    if "default_account_id" in payload:
        default_account_id_raw = payload.get("default_account_id")
        default_account_id = (
            int(default_account_id_raw) if default_account_id_raw is not None else None
        )
        default_account_id = _validate_default_account_for_flow(default_account_id, next_flow)
        updates.append("default_account_id = ?")
        values.append(default_account_id)

    if not updates:
        return existing

    with connect() as conn:
        if next_name is not None:
            duplicate = conn.execute(
                "SELECT id FROM categories WHERE name = ? AND id != ?",
                (next_name, category_id),
            ).fetchone()
            if duplicate is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail="category name already exists"
                )
        conn.execute(
            f"UPDATE categories SET {', '.join(updates)}, updated_at = ? WHERE id = ?",
            [*values, _now_ts(), category_id],
        )
        conn.commit()
    return get_category(category_id)


def delete_category(category_id: int, *, confirm: bool) -> None:
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="confirm must be true to delete category",
        )
    get_category(category_id)
    with connect() as conn:
        conn.execute(
            "UPDATE transaction_lines SET category_id = NULL WHERE category_id = ?", (category_id,)
        )
        conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        conn.commit()


def assign_category_to_line(line_id: int, category_id: int | None) -> dict[str, Any]:
    ensure_categories_tables()
    selected_id = category_id
    if selected_id is not None:
        get_category(selected_id)
    with connect() as conn:
        line = conn.execute(
            "SELECT id, transaction_id, account_id, category_id "
            "FROM transaction_lines WHERE id = ?",
            (line_id,),
        ).fetchone()
        if line is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="transaction line not found"
            )
        conn.execute(
            "UPDATE transaction_lines SET category_id = ? WHERE id = ?", (selected_id, line_id)
        )
        conn.commit()
        updated = conn.execute(
            "SELECT id, transaction_id, account_id, category_id "
            "FROM transaction_lines WHERE id = ?",
            (line_id,),
        ).fetchone()
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="line update failed"
        )
    return dict(updated)
