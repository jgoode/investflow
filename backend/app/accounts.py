from __future__ import annotations

import re
import sqlite3
import time
from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from fastapi import HTTPException, status

from app.crypto_store import write_account_sensitive
from app.db.connection import connect

ACCOUNT_TYPES = ("asset", "liability", "income", "expense", "equity")
ACCOUNT_SUBTYPES = ("group", "bank", "cash", "brokerage", "credit_card", "fund", "other")
ROOT_ACCOUNT_TYPES = set(ACCOUNT_TYPES)

SEED_ACCOUNTS: list[dict[str, Any]] = [
    {
        "code": "ROOT-ASSET",
        "name": "Assets",
        "type": "asset",
        "subtype": "group",
        "parent_code": None,
        "institution": None,
        "description": "Asset root",
        "is_investment": False,
    },
    {
        "code": "ROOT-LIABILITY",
        "name": "Liabilities",
        "type": "liability",
        "subtype": "group",
        "parent_code": None,
        "institution": None,
        "description": "Liability root",
        "is_investment": False,
    },
    {
        "code": "ROOT-INCOME",
        "name": "Income",
        "type": "income",
        "subtype": "group",
        "parent_code": None,
        "institution": None,
        "description": "Income root",
        "is_investment": False,
    },
    {
        "code": "ROOT-EXPENSE",
        "name": "Expenses",
        "type": "expense",
        "subtype": "group",
        "parent_code": None,
        "institution": None,
        "description": "Expense root",
        "is_investment": False,
    },
    {
        "code": "ROOT-EQUITY",
        "name": "Equity",
        "type": "equity",
        "subtype": "group",
        "parent_code": None,
        "institution": None,
        "description": "Equity root",
        "is_investment": False,
    },
    {
        "code": "CASH-01",
        "name": "Cash",
        "type": "asset",
        "subtype": "cash",
        "parent_code": "ROOT-ASSET",
        "institution": None,
        "description": "Primary cash holdings",
        "is_investment": False,
    },
    {
        "code": "BANK-GROUP",
        "name": "Bank Accounts",
        "type": "asset",
        "subtype": "group",
        "parent_code": "ROOT-ASSET",
        "institution": None,
        "description": "Banking account group",
        "is_investment": False,
    },
    {
        "code": "BANK-01",
        "name": "Bank A",
        "type": "asset",
        "subtype": "bank",
        "parent_code": "BANK-GROUP",
        "institution": "Demo Bank",
        "description": "Primary bank account",
        "is_investment": False,
    },
    {
        "code": "INVEST-GROUP",
        "name": "Investments",
        "type": "asset",
        "subtype": "group",
        "parent_code": "ROOT-ASSET",
        "institution": None,
        "description": "Investment group",
        "is_investment": False,
    },
    {
        "code": "BROKERAGE-01",
        "name": "Brokerage A",
        "type": "asset",
        "subtype": "brokerage",
        "parent_code": "INVEST-GROUP",
        "institution": None,
        "description": "Brokerage account",
        "is_investment": True,
    },
    {
        "code": "CC-GROUP",
        "name": "Credit Cards",
        "type": "liability",
        "subtype": "group",
        "parent_code": "ROOT-LIABILITY",
        "institution": None,
        "description": "Credit card grouping",
        "is_investment": False,
    },
    {
        "code": "CC-01",
        "name": "Credit Card A",
        "type": "liability",
        "subtype": "credit_card",
        "parent_code": "CC-GROUP",
        "institution": "Demo Bank",
        "description": "Credit card account",
        "is_investment": False,
    },
    {
        "code": "LOAN-GROUP",
        "name": "Loans",
        "type": "liability",
        "subtype": "group",
        "parent_code": "ROOT-LIABILITY",
        "institution": None,
        "description": "Loan grouping",
        "is_investment": False,
    },
    {
        "code": "LOAN-01",
        "name": "Loan A",
        "type": "liability",
        "subtype": "other",
        "parent_code": "LOAN-GROUP",
        "institution": None,
        "description": "Loan account",
        "is_investment": False,
    },
    {
        "code": "INCOME-SALARY",
        "name": "Salary",
        "type": "income",
        "subtype": "other",
        "parent_code": "ROOT-INCOME",
        "institution": None,
        "description": "Salary income",
        "is_investment": False,
    },
    {
        "code": "INCOME-INTDIV",
        "name": "Interest & Dividends",
        "type": "income",
        "subtype": "other",
        "parent_code": "ROOT-INCOME",
        "institution": None,
        "description": "Interest and dividends",
        "is_investment": False,
    },
    {
        "code": "INCOME-REALIZED",
        "name": "Realized Gains",
        "type": "income",
        "subtype": "other",
        "parent_code": "ROOT-INCOME",
        "institution": None,
        "description": "Realized gains",
        "is_investment": False,
    },
    {
        "code": "INCOME-OTHER",
        "name": "Other Income",
        "type": "income",
        "subtype": "other",
        "parent_code": "ROOT-INCOME",
        "institution": None,
        "description": "Other income",
        "is_investment": False,
    },
    {
        "code": "EXP-HOUSING",
        "name": "Housing",
        "type": "expense",
        "subtype": "other",
        "parent_code": "ROOT-EXPENSE",
        "institution": None,
        "description": "Housing expense",
        "is_investment": False,
    },
    {
        "code": "EXP-FOOD",
        "name": "Food",
        "type": "expense",
        "subtype": "other",
        "parent_code": "ROOT-EXPENSE",
        "institution": None,
        "description": "Food expense",
        "is_investment": False,
    },
    {
        "code": "EXP-TRANSPORT",
        "name": "Transportation",
        "type": "expense",
        "subtype": "other",
        "parent_code": "ROOT-EXPENSE",
        "institution": None,
        "description": "Transportation expense",
        "is_investment": False,
    },
    {
        "code": "EXP-UTILITIES",
        "name": "Utilities",
        "type": "expense",
        "subtype": "other",
        "parent_code": "ROOT-EXPENSE",
        "institution": None,
        "description": "Utilities expense",
        "is_investment": False,
    },
    {
        "code": "EXP-HEALTH",
        "name": "Healthcare",
        "type": "expense",
        "subtype": "other",
        "parent_code": "ROOT-EXPENSE",
        "institution": None,
        "description": "Healthcare expense",
        "is_investment": False,
    },
    {
        "code": "EXP-INSURANCE",
        "name": "Insurance",
        "type": "expense",
        "subtype": "other",
        "parent_code": "ROOT-EXPENSE",
        "institution": None,
        "description": "Insurance expense",
        "is_investment": False,
    },
    {
        "code": "EXP-ENTERTAINMENT",
        "name": "Entertainment",
        "type": "expense",
        "subtype": "other",
        "parent_code": "ROOT-EXPENSE",
        "institution": None,
        "description": "Entertainment expense",
        "is_investment": False,
    },
    {
        "code": "EXP-TRAVEL",
        "name": "Travel",
        "type": "expense",
        "subtype": "other",
        "parent_code": "ROOT-EXPENSE",
        "institution": None,
        "description": "Travel expense",
        "is_investment": False,
    },
    {
        "code": "EXP-EDUCATION",
        "name": "Education",
        "type": "expense",
        "subtype": "other",
        "parent_code": "ROOT-EXPENSE",
        "institution": None,
        "description": "Education expense",
        "is_investment": False,
    },
    {
        "code": "EXP-FEES",
        "name": "Fees",
        "type": "expense",
        "subtype": "other",
        "parent_code": "ROOT-EXPENSE",
        "institution": None,
        "description": "Fees expense",
        "is_investment": False,
    },
    {
        "code": "EXP-OTHER",
        "name": "Other Expenses",
        "type": "expense",
        "subtype": "other",
        "parent_code": "ROOT-EXPENSE",
        "institution": None,
        "description": "Other expense",
        "is_investment": False,
    },
    {
        "code": "EQUITY-OPEN",
        "name": "Opening Balance",
        "type": "equity",
        "subtype": "other",
        "parent_code": "ROOT-EQUITY",
        "institution": None,
        "description": "Opening balance equity",
        "is_investment": False,
    },
]


def _now_ts() -> int:
    return int(time.time())


def _normalize_code(value: str) -> str:
    return value.strip()


def _derive_last4(value: str | None) -> str | None:
    if value is None:
        return None
    digits = re.sub(r"\D", "", value)
    return digits[-4:] if digits else None


def ensure_accounts_table() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY,
                code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                type TEXT NOT NULL CHECK(
                    type IN ('asset', 'liability', 'income', 'expense', 'equity')
                ),
                subtype TEXT NOT NULL CHECK(
                    subtype IN ('group', 'bank', 'cash', 'brokerage', 'credit_card',
                    'fund', 'other')
                ),
                parent_id INTEGER NULL,
                institution TEXT NULL,
                description TEXT NULL,
                last4 TEXT NULL,
                is_archived INTEGER NOT NULL DEFAULT 0,
                is_investment INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY(parent_id) REFERENCES accounts(id) ON DELETE SET NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seed_meta (
                name TEXT PRIMARY KEY,
                version INTEGER NOT NULL,
                applied_at INTEGER NOT NULL
            )
            """
        )
        conn.commit()


def _serialize_account(row: sqlite3.Row | Mapping[str, Any]) -> dict[str, Any]:
    item = dict(row)
    for key in ("is_archived", "is_investment"):
        if key in item:
            item[key] = bool(int(item[key] or 0))
    return item


def _fetch_account_by_id(account_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM accounts WHERE id = ?",
            (account_id,),
        ).fetchone()
    if row is None:
        return None
    return _serialize_account(row)


def _fetch_account_by_code(code: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM accounts WHERE code = ?",
            (_normalize_code(code),),
        ).fetchone()
    if row is None:
        return None
    return _serialize_account(row)


def _extract_seed_parent_id(conn: sqlite3.Connection, parent_code: str | None) -> int | None:
    if parent_code is None:
        return None
    row = conn.execute("SELECT id FROM accounts WHERE code = ?", (parent_code,)).fetchone()
    if row is None:
        return None
    return int(row["id"])


def ensure_seeded_coa() -> list[dict[str, Any]]:
    ensure_accounts_table()
    with connect() as conn:
        existing = conn.execute("SELECT version FROM seed_meta WHERE name = 'coa_v1'").fetchone()
        if existing is not None:
            rows = conn.execute("SELECT * FROM accounts ORDER BY id ASC").fetchall()
            return [_serialize_account(row) for row in rows]

        now = _now_ts()
        for item in SEED_ACCOUNTS:
            parent_id = None
            if item["parent_code"] is not None:
                parent_id = _extract_seed_parent_id(conn, item["parent_code"])
            conn.execute(
                """
                INSERT OR IGNORE INTO accounts (
                    code, name, type, subtype, parent_id, institution, description,
                    last4, is_archived, is_investment, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
                """,
                (
                    item["code"],
                    item["name"],
                    item["type"],
                    item["subtype"],
                    parent_id,
                    item["institution"],
                    item["description"],
                    None,
                    1 if item["is_investment"] else 0,
                    now,
                    now,
                ),
            )
        conn.execute(
            "INSERT OR REPLACE INTO seed_meta (name, version, applied_at) VALUES ('coa_v1', 1, ?)",
            (now,),
        )
        conn.commit()
        rows = conn.execute("SELECT * FROM accounts ORDER BY id ASC").fetchall()
        return [_serialize_account(row) for row in rows]


def validate_account_payload(
    *,
    code: str,
    name: str,
    account_type: str,
    subtype: str,
    parent_id: int | None,
) -> None:
    if account_type not in ACCOUNT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid account type"
        )
    if subtype not in ACCOUNT_SUBTYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid account subtype"
        )
    if not code.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="account code is required"
        )
    if not name.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="account name is required"
        )
    if parent_id is not None:
        parent = _fetch_account_by_id(parent_id)
        if parent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="parent account not found"
            )
        if parent["type"] != account_type:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="account type must match parent branch",
            )
    if account_type not in ROOT_ACCOUNT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid account type"
        )


def account_tree() -> dict[str, Any]:
    ensure_seeded_coa()
    with connect() as conn:
        rows = conn.execute("SELECT * FROM accounts ORDER BY name ASC").fetchall()
    accounts = [_serialize_account(row) for row in rows]
    by_parent: dict[int | None, list[dict[str, Any]]] = defaultdict(list)
    for row in accounts:
        by_parent[int(row["parent_id"]) if row["parent_id"] is not None else None].append(row)

    def build(node_id: int | None) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for row in by_parent.get(node_id, []):
            row_payload = dict(row)
            row_payload["children"] = build(int(row["id"]))
            result.append(row_payload)
        return result

    return {"tree": build(None)}


def update_account_details(account_id: int, *, payload: Mapping[str, Any]) -> dict[str, Any]:
    target = _fetch_account_by_id(account_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="account not found")
    updates: list[str] = []
    values: list[Any] = []
    for field in (
        "code",
        "name",
        "type",
        "subtype",
        "parent_id",
        "institution",
        "description",
        "is_archived",
        "is_investment",
    ):
        if field not in payload:
            continue
        updates.append(f"{field} = ?")
        values.append(payload[field])
    if not updates:
        return target
    if "code" in payload and not str(payload["code"]).strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="account code is required"
        )
    if "name" in payload and not str(payload["name"]).strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="account name is required"
        )
    if "type" in payload or "parent_id" in payload:
        next_type = str(payload.get("type", target["type"]))
        next_parent = payload.get("parent_id", target["parent_id"])
        if next_parent is not None:
            parent = _fetch_account_by_id(int(next_parent))
            if parent is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="parent account not found"
                )
            if parent["type"] != next_type:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="account type must match parent branch",
                )
    with connect() as conn:
        conn.execute(
            f"UPDATE accounts SET {', '.join(updates)}, updated_at = ? WHERE id = ?",
            [*values, _now_ts(), account_id],
        )
        conn.commit()

    updated = _fetch_account_by_id(account_id)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="account not found")
    return updated


def create_account(payload: Mapping[str, Any]) -> dict[str, Any]:
    code = _normalize_code(str(payload.get("code", "")))
    name = str(payload.get("name", "")).strip()
    account_type = str(payload.get("type", "")).strip().lower()
    subtype = str(payload.get("subtype", "group")).strip().lower()
    parent_id = payload.get("parent_id")
    if parent_id is not None:
        parent_id = int(parent_id)
    validate_account_payload(
        code=code, name=name, account_type=account_type, subtype=subtype, parent_id=parent_id
    )
    if _fetch_account_by_code(code) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="account code already exists"
        )

    last4 = _derive_last4(str(payload.get("account_number") or ""))
    is_investment = bool(payload.get("is_investment", False)) or subtype in {"brokerage", "fund"}
    now = _now_ts()
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO accounts (
                code, name, type, subtype, parent_id, institution, description, last4,
                is_archived, is_investment, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
            """,
            (
                code,
                name,
                account_type,
                subtype,
                parent_id,
                payload.get("institution"),
                payload.get("description"),
                last4,
                1 if is_investment else 0,
                now,
                now,
            ),
        )
        conn.commit()
        last_row_id = cursor.lastrowid
        if last_row_id is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="account create failed"
            )
        account_id = int(last_row_id)

    sensitive_values = {
        field: payload.get(field)
        for field in ("account_number", "routing_transit", "transfer_numbers", "notes")
    }
    sensitive_payload = {
        "account_number_enc": sensitive_values.get("account_number"),
        "routing_transit_enc": sensitive_values.get("routing_transit"),
        "transfer_numbers_enc": sensitive_values.get("transfer_numbers"),
        "notes_enc": sensitive_values.get("notes"),
    }
    if any(value is not None for value in sensitive_values.values()):
        write_account_sensitive(account_id, sensitive_payload)
    created = _fetch_account_by_id(account_id)
    if created is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="account create failed"
        )
    return created
