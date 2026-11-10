from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from fastapi import HTTPException, status

from app.db.connection import connect

POSITION_OPEN = "open"
POSITION_CLOSED = "closed"


def average_cost_after_trade(
    *,
    prior_quantity_q4: int,
    prior_avg_cost_q4: int,
    quantity_q4: int,
    price_q4: int,
    fee_cents: int,
) -> int:
    if prior_quantity_q4 < 0 or quantity_q4 < 0 or prior_avg_cost_q4 < 0 or price_q4 < 0:
        raise ValueError("position inputs must be non-negative")
    if fee_cents < 0:
        raise ValueError("fee_cents must be non-negative")
    if quantity_q4 == 0:
        return prior_avg_cost_q4
    total_quantity_q4 = prior_quantity_q4 + quantity_q4
    if total_quantity_q4 == 0:
        return prior_avg_cost_q4
    total_cost_q4 = (
        prior_quantity_q4 * prior_avg_cost_q4 + quantity_q4 * price_q4 + fee_cents * 100 * 10_000
    )
    return total_cost_q4 // total_quantity_q4


def realized_gain_loss_cents(*, sold_quantity_q4: int, avg_cost_q4: int, sell_price_q4: int) -> int:
    if sold_quantity_q4 <= 0:
        return 0
    return (sold_quantity_q4 * (sell_price_q4 - avg_cost_q4)) // 1_000_000


def ensure_positions_tables() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY,
                account_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                quantity_q4 INTEGER NOT NULL CHECK(quantity_q4 >= 0),
                avg_cost_q4 INTEGER NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('open', 'closed')) DEFAULT 'open',
                realized_gain_loss_cents INTEGER NOT NULL DEFAULT 0,
                last_price_q4 INTEGER NOT NULL DEFAULT 0,
                last_trade_date TEXT NOT NULL DEFAULT '',
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE,
                UNIQUE(account_id, ticker)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS ix_positions_account_id ON positions(account_id)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_positions_account_status "
            "ON positions(account_id, status)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS ix_positions_ticker ON positions(ticker)")
        conn.commit()


def _now_ts() -> int:
    import time

    return int(time.time())


def _current_date_iso() -> str:
    return date.today().isoformat()


def _position_market_value_cents(row: dict[str, Any]) -> int:
    if int(row.get("quantity_q4") or 0) <= 0:
        return 0
    last_price_q4 = int(row.get("last_price_q4") or 0)
    if last_price_q4 <= 0:
        return 0
    return (int(row["quantity_q4"]) * last_price_q4) // 1_000_000


def _serialize_position(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "account_id": int(row["account_id"]),
        "account_name": row.get("account_name"),
        "ticker": row["ticker"],
        "quantity_q4": int(row["quantity_q4"]),
        "avg_cost_q4": int(row["avg_cost_q4"]),
        "status": row["status"],
        "realized_gain_loss_cents": int(row.get("realized_gain_loss_cents") or 0),
        "last_price_q4": int(row.get("last_price_q4") or 0),
        "last_trade_date": row.get("last_trade_date") or "",
        "market_value_cents": _position_market_value_cents(row),
        "created_at": int(row["created_at"]),
        "updated_at": int(row["updated_at"]),
    }


def _account_is_brokerage(account_row: dict[str, Any] | None) -> bool:
    if account_row is None:
        return False
    return str(account_row.get("subtype") or "").lower() == "brokerage" or bool(
        int(account_row.get("is_investment") or 0)
    )


def list_positions() -> dict[str, Any]:
    ensure_positions_tables()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT p.*, a.name AS account_name
            FROM positions p
            JOIN accounts a ON a.id = p.account_id
            WHERE p.status = 'open'
            ORDER BY a.name ASC, p.ticker ASC
            """
        ).fetchall()

    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in (dict(existing) for existing in rows):
        grouped[int(row["account_id"])].append(_serialize_position(row))

    account_groups: list[dict[str, Any]] = []
    overall_total = 0
    for account_id, positions in sorted(
        grouped.items(),
        key=lambda item: (
            -sum(position["market_value_cents"] for position in item[1]),
            int(item[0]),
        ),
    ):
        account_rows = positions
        total = sum(position["market_value_cents"] for position in account_rows)
        overall_total += total
        account_groups.append(
            {
                "account_id": account_id,
                "account_name": account_rows[0]["account_name"],
                "total_market_value_cents": total,
                "positions": sorted(
                    account_rows, key=lambda row: (-row["market_value_cents"], row["ticker"])
                ),
            }
        )

    account_groups.sort(
        key=lambda entry: (-int(entry["total_market_value_cents"]), str(entry["account_name"]))
    )
    return {
        "account_groups": account_groups,
        "overall_total_market_value_cents": overall_total,
    }


def apply_trade_on_connection(
    conn: Any,
    *,
    account_id: int,
    ticker: str,
    side: str,
    quantity_q4: int,
    price_q4: int,
    fee_cents: int,
    trade_date: str | None = None,
) -> dict[str, Any]:
    """Apply a buy/sell to the position tables on the caller's open connection.

    The caller owns the transaction (BEGIN IMMEDIATE + commit/rollback), which
    lets the importer run a whole file atomically (AC-IMP1c). Raises
    HTTPException (422/404) on oversell, archived accounts, non-brokerage
    accounts, and missing positions — the caller decides how to surface them.
    """
    normalized_side = str(side).strip().lower()
    if normalized_side not in {"buy", "sell"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="side must be buy or sell",
        )
    if quantity_q4 <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="quantity_q4 must be positive",
        )
    if price_q4 <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="price_q4 must be positive",
        )
    if fee_cents < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="fee_cents cannot be negative",
        )

    account_row = conn.execute(
        "SELECT id, subtype, is_investment, is_archived FROM accounts WHERE id = ?",
        (account_id,),
    ).fetchone()
    if account_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="account not found")
    if bool(account_row["is_archived"]):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="account is archived",
        )
    if not _account_is_brokerage(dict(account_row)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="account is not investment/brokerage",
        )

    ticker_name = str(ticker or "").strip().upper()
    if not ticker_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="ticker is required",
        )

    row = conn.execute(
        "SELECT * FROM positions WHERE account_id = ? AND ticker = ?",
        (account_id, ticker_name),
    ).fetchone()
    now = _now_ts()
    trade_on = trade_date or _current_date_iso()

    if normalized_side == "buy":
        if row is None:
            next_avg = average_cost_after_trade(
                prior_quantity_q4=0,
                prior_avg_cost_q4=0,
                quantity_q4=quantity_q4,
                price_q4=price_q4,
                fee_cents=fee_cents,
            )
            conn.execute(
                """
                INSERT INTO positions (
                    account_id, ticker, quantity_q4, avg_cost_q4, status,
                    realized_gain_loss_cents, last_price_q4, last_trade_date,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
                """,
                (
                    account_id,
                    ticker_name,
                    quantity_q4,
                    next_avg,
                    POSITION_OPEN,
                    price_q4,
                    trade_on,
                    now,
                    now,
                ),
            )
        else:
            prior_qty = int(row["quantity_q4"])
            prior_avg = int(row["avg_cost_q4"])
            next_avg = average_cost_after_trade(
                prior_quantity_q4=prior_qty,
                prior_avg_cost_q4=prior_avg,
                quantity_q4=quantity_q4,
                price_q4=price_q4,
                fee_cents=fee_cents,
            )
            new_qty = prior_qty + quantity_q4
            conn.execute(
                """
                UPDATE positions
                SET quantity_q4 = ?,
                    avg_cost_q4 = ?,
                    status = ?,
                    last_price_q4 = ?,
                    last_trade_date = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (new_qty, next_avg, POSITION_OPEN, price_q4, trade_on, now, row["id"]),
            )
        created_row = conn.execute(
            "SELECT * FROM positions WHERE account_id = ? AND ticker = ?",
            (account_id, ticker_name),
        ).fetchone()
        position = _serialize_position(dict(created_row))
        return {
            "position": position,
            "realized_gain_loss_cents": 0,
            "trade": {
                "account_id": account_id,
                "ticker": ticker_name,
                "side": normalized_side,
                "quantity_q4": quantity_q4,
                "price_q4": price_q4,
                "fee_cents": fee_cents,
                "trade_date": trade_on,
            },
        }

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="position not found for this account/ticker",
        )

    current_qty = int(row["quantity_q4"])
    if current_qty < quantity_q4:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="sell quantity exceeds current position quantity",
        )

    avg_cost_q4 = int(row["avg_cost_q4"])
    realized = realized_gain_loss_cents(
        sold_quantity_q4=quantity_q4,
        avg_cost_q4=avg_cost_q4,
        sell_price_q4=price_q4,
    )
    new_qty = current_qty - quantity_q4
    next_status = POSITION_OPEN if new_qty > 0 else POSITION_CLOSED
    next_avg_cost = avg_cost_q4 if new_qty > 0 else 0
    new_realized_total = int(row["realized_gain_loss_cents"]) + realized
    conn.execute(
        """
        UPDATE positions
        SET quantity_q4 = ?,
            avg_cost_q4 = ?,
            status = ?,
            realized_gain_loss_cents = ?,
            last_price_q4 = ?,
            last_trade_date = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            new_qty,
            next_avg_cost,
            next_status,
            new_realized_total,
            price_q4,
            trade_on,
            now,
            row["id"],
        ),
    )
    updated_row = conn.execute(
        "SELECT * FROM positions WHERE account_id = ? AND ticker = ?",
        (account_id, ticker_name),
    ).fetchone()
    position = _serialize_position(dict(updated_row))
    return {
        "position": position,
        "realized_gain_loss_cents": realized,
        "trade": {
            "account_id": account_id,
            "ticker": ticker_name,
            "side": normalized_side,
            "quantity_q4": quantity_q4,
            "price_q4": price_q4,
            "fee_cents": fee_cents,
            "trade_date": trade_on,
        },
    }


def apply_manual_trade(
    *,
    account_id: int,
    ticker: str,
    side: str,
    quantity_q4: int,
    price_q4: int,
    fee_cents: int,
    trade_date: str | None = None,
) -> dict[str, Any]:
    ensure_positions_tables()
    with connect() as conn:
        result = apply_trade_on_connection(
            conn,
            account_id=account_id,
            ticker=ticker,
            side=side,
            quantity_q4=quantity_q4,
            price_q4=price_q4,
            fee_cents=fee_cents,
            trade_date=trade_date,
        )
        conn.commit()
    return result
