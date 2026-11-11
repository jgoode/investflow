"""Dry-run evaluator: turns parsed CSV + mapping + bindings into a normalized
row plan with per-row errors, duplicates, effects, and absent-holding flags
(AC-IMP1b). Pure with respect to the database — it only reads current state.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.positions import POSITION_OPEN, average_cost_after_trade, realized_gain_loss_cents
from app.services.importer import dedupe, parser
from app.services.importer.dedupe import trade_row_hash
from app.services.importer.mapping import resolve_effective_mapping

TRADE_TYPES = {"buy", "sell", "dividend", "fee"}


def _cell(row: dict[str, str], mapping: dict[str, str | None], field: str) -> str | None:
    column = mapping.get(field)
    if column is None:
        return None
    return row.get(str(column).casefold())


def _require_date(raw: str | None, errors: list[str]) -> str | None:
    if raw is None:
        errors.append("date column is not mapped")
        return None
    text = raw.strip()
    try:
        date.fromisoformat(text)
    except ValueError:
        errors.append(f"date must use ISO format YYYY-MM-DD: {text!r}")
        return None
    return text


def _resolve_account(
    label: str | None,
    bindings: dict[str, int],
    errors: list[str],
    *,
    what: str = "account",
) -> int | None:
    if label is None:
        errors.append(f"{what} column is not mapped")
        return None
    key = label.strip()
    account_id = bindings.get(key)
    if account_id is None:
        errors.append(f"no account binding for {what} {key!r}; map it in the import wizard")
        return None
    return account_id


def build_positions_plan(
    conn: Any,
    *,
    parsed: parser.CsvFile,
    column_mapping: dict[str, str | None],
    bindings: dict[str, int],
) -> dict[str, Any]:
    """Normalize a positions snapshot and flag holdings absent from it."""
    rows: list[dict[str, Any]] = []
    for index, raw in enumerate(parsed.rows, start=1):
        errors: list[str] = []
        account_label = _cell(raw, column_mapping, "account")
        ticker = (_cell(raw, column_mapping, "ticker") or "").strip().upper()
        if not ticker:
            errors.append("ticker is required")
        account_id = _resolve_account(account_label, bindings, errors)

        quantity_q4: int | None = None
        quantity_raw = _cell(raw, column_mapping, "quantity")
        if quantity_raw is None:
            errors.append("quantity column is not mapped")
        else:
            try:
                quantity_q4 = parser.decimal_to_q4(quantity_raw, label="quantity")
            except parser.ImportError as exc:
                errors.append(str(exc))

        avg_cost_q4 = 0
        avg_cost_raw = _cell(raw, column_mapping, "avg_cost")
        if avg_cost_raw is not None and avg_cost_raw.strip():
            try:
                avg_cost_q4 = parser.decimal_to_q4(avg_cost_raw, label="avg cost")
            except parser.ImportError as exc:
                errors.append(str(exc))

        row: dict[str, Any] = {
            "row_index": index,
            "kind": "positions",
            "account_label": account_label,
            "account_id": account_id,
            "ticker": ticker,
            "quantity_q4": quantity_q4,
            "avg_cost_q4": avg_cost_q4,
            "errors": errors,
            "duplicate": False,
        }
        row["hash"] = trade_row_hash(
            {
                "account_id": account_id,
                "ticker": ticker,
                "quantity_q4": quantity_q4,
                "avg_cost_q4": avg_cost_q4,
            }
        )
        if not errors and account_id is not None:
            row["effect"] = {
                "action": "snapshot",
                "account": account_label,
                "ticker": ticker,
                "quantity_q4": quantity_q4,
                "avg_cost_q4": avg_cost_q4,
            }
        rows.append(row)

    csv_keys = {
        (row["account_id"], row["ticker"]) for row in rows if row["account_id"] and row["ticker"]
    }
    bound_ids = sorted({row["account_id"] for row in rows if row["account_id"]})
    absent_holdings: list[dict[str, Any]] = []
    if bound_ids:
        placeholders = ",".join("?" for _ in bound_ids)
        open_rows = conn.execute(
            "SELECT account_id, ticker FROM positions "
            f"WHERE status = '{POSITION_OPEN}' AND account_id IN ({placeholders}) "
            "ORDER BY account_id, ticker",
            tuple(bound_ids),
        ).fetchall()
        for open_row in open_rows:
            key = (int(open_row["account_id"]), str(open_row["ticker"]))
            if key not in csv_keys:
                absent_holdings.append({"account_id": key[0], "ticker": key[1]})

    return {"rows": rows, "absent_holdings": absent_holdings}


def build_trades_plan(
    conn: Any,
    *,
    parsed: parser.CsvFile,
    column_mapping: dict[str, str | None],
    bindings: dict[str, int],
    committed_hashes: set[str],
) -> dict[str, Any]:
    """Normalize trade rows, resolve bindings, simulate the position engine, and
    mark duplicates against the committed hash registry."""
    rows: list[dict[str, Any]] = []
    state: dict[tuple[int, str], dict[str, int]] = {}

    def _position_state(account_id: int, ticker: str) -> dict[str, int]:
        key = (account_id, ticker)
        if key not in state:
            db_row = conn.execute(
                "SELECT quantity_q4, avg_cost_q4, realized_gain_loss_cents FROM positions "
                "WHERE account_id = ? AND ticker = ?",
                (account_id, ticker),
            ).fetchone()
            state[key] = {
                "quantity_q4": int(db_row["quantity_q4"]) if db_row else 0,
                "avg_cost_q4": int(db_row["avg_cost_q4"]) if db_row else 0,
                "realized_gain_loss_cents": int(db_row["realized_gain_loss_cents"])
                if db_row
                else 0,
            }
        return state[key]

    for index, raw in enumerate(parsed.rows, start=1):
        errors: list[str] = []
        date_value = _require_date(_cell(raw, column_mapping, "date"), errors)
        type_raw = (_cell(raw, column_mapping, "type") or "").strip().lower()
        row_type = type_raw if type_raw in TRADE_TYPES else None
        if row_type is None:
            errors.append(
                f"side must be one of buy, sell, dividend, fee: {type_raw!r}"
                if type_raw
                else "side (type) column is not mapped"
            )
        ticker = (_cell(raw, column_mapping, "ticker") or "").strip().upper()
        if not ticker:
            errors.append("ticker is required")
        cash_label = _cell(raw, column_mapping, "cash_account")
        account_id = _resolve_account(cash_label, bindings, errors, what="cash account")

        quantity_q4: int | None = None
        price_q4: int | None = None
        fee_cents: int | None = None
        amount_cents: int | None = None

        if row_type in {"buy", "sell"}:
            quantity_raw = _cell(raw, column_mapping, "quantity")
            if quantity_raw is None:
                errors.append("quantity is required for buy/sell rows")
            else:
                try:
                    quantity_q4 = parser.decimal_to_q4(quantity_raw, label="quantity")
                except parser.ImportError as exc:
                    errors.append(str(exc))
            price_raw = _cell(raw, column_mapping, "price")
            if price_raw is None:
                errors.append("price is required for buy/sell rows")
            else:
                try:
                    price_q4 = parser.decimal_to_q4(price_raw, label="price")
                except parser.ImportError as exc:
                    errors.append(str(exc))
            fee_raw = _cell(raw, column_mapping, "fee")
            if fee_raw is not None and fee_raw.strip():
                try:
                    fee_cents = parser.decimal_to_cents(fee_raw, label="fee")
                except parser.ImportError as exc:
                    errors.append(str(exc))
            else:
                fee_cents = 0

        if row_type in {"dividend", "fee"}:
            amount_raw = _cell(raw, column_mapping, "amount")
            if amount_raw is None:
                errors.append(f"amount column is not mapped (required for {row_type} rows)")
            else:
                try:
                    amount_cents = parser.decimal_to_cents(amount_raw, label="amount")
                except parser.ImportError as exc:
                    errors.append(str(exc))

        row: dict[str, Any] = {
            "row_index": index,
            "kind": "trades",
            "date": date_value,
            "type": row_type,
            "ticker": ticker,
            "quantity_q4": quantity_q4,
            "price_q4": price_q4,
            "fee_cents": fee_cents,
            "amount_cents": amount_cents,
            "account_label": cash_label,
            "account_id": account_id,
            "cash_account_id": account_id,
            "errors": errors,
            "duplicate": False,
        }
        row["hash"] = trade_row_hash(row)

        if not errors and row_type is not None and account_id is not None:
            if row["hash"] in committed_hashes:
                row["duplicate"] = True
            elif any(existing["hash"] == row["hash"] for existing in rows):
                row["duplicate"] = True

        effect = _simulate_trade_row(row, _position_state)
        if effect is not None:
            row["effect"] = effect
        rows.append(row)

    return {"rows": rows}


def _simulate_trade_row(row: dict[str, Any], position_state: Any) -> dict[str, Any] | None:
    """Advance the in-memory position state for one valid trade row (dry run)."""
    if row["errors"] or row["duplicate"]:
        return None
    account_id, ticker = row["account_id"], row["ticker"]
    if account_id is None or not ticker:
        return None

    if row["type"] in {"buy", "sell"}:
        current = position_state(account_id, ticker)
        prior_quantity_q4 = current["quantity_q4"]
        prior_avg_cost_q4 = current["avg_cost_q4"]
        quantity_q4 = int(row["quantity_q4"] or 0)
        price_q4 = int(row["price_q4"] or 0)
        fee_cents = int(row["fee_cents"] or 0)

        if row["type"] == "sell":
            if prior_quantity_q4 < quantity_q4:
                row["errors"].append(
                    f"sell quantity {quantity_q4 / 10000:g} exceeds current position "
                    f"quantity {prior_quantity_q4 / 10000:g} for {ticker}"
                )
                return None
            realized = realized_gain_loss_cents(
                sold_quantity_q4=quantity_q4,
                avg_cost_q4=prior_avg_cost_q4,
                sell_price_q4=price_q4,
            )
            new_qty = prior_quantity_q4 - quantity_q4
            current["realized_gain_loss_cents"] += realized
            current["avg_cost_q4"] = prior_avg_cost_q4 if new_qty > 0 else 0
        else:
            realized = 0
            current["avg_cost_q4"] = average_cost_after_trade(
                prior_quantity_q4=prior_quantity_q4,
                prior_avg_cost_q4=prior_avg_cost_q4,
                quantity_q4=quantity_q4,
                price_q4=price_q4,
                fee_cents=fee_cents,
            )
            new_qty = prior_quantity_q4 + quantity_q4
        current["quantity_q4"] = new_qty
        return {
            "action": row["type"],
            "account": row["account_label"],
            "ticker": ticker,
            "quantity_q4": quantity_q4,
            "price_q4": price_q4,
            "fee_cents": fee_cents,
            "resulting_quantity_q4": new_qty,
            "realized_gain_loss_cents": realized,
        }

    if row["type"] in {"dividend", "fee"}:
        return {
            "action": row["type"],
            "account": row["account_label"],
            "ticker": ticker,
            "amount_cents": int(row["amount_cents"] or 0),
        }
    return None


def build_price_history_plan(
    conn: Any,
    *,
    parsed: parser.CsvFile,
    column_mapping: dict[str, str | None],
    committed_hashes: set[str],
) -> dict[str, Any]:
    """Normalize daily close/volume rows for the ``price_history`` kind (AC-IMP1h).

    Price rows are not account-bound and carry no replay-order semantics; a
    (ticker, date) close upserts into price_cache. Duplicates are marked against
    the committed hash registry and against identical rows earlier in the file.
    """
    rows: list[dict[str, Any]] = []
    for index, raw in enumerate(parsed.rows, start=1):
        errors: list[str] = []
        date_value = _require_date(_cell(raw, column_mapping, "date"), errors)
        ticker = (_cell(raw, column_mapping, "ticker") or "").strip().upper()
        if not ticker:
            errors.append("ticker is required")

        close_q4: int | None = None
        close_raw = _cell(raw, column_mapping, "close")
        if close_raw is None:
            errors.append("close column is not mapped")
        else:
            try:
                close_q4 = parser.decimal_to_q4(close_raw, label="close")
            except parser.ImportError as exc:
                errors.append(str(exc))

        volume = 0
        volume_raw = _cell(raw, column_mapping, "volume")
        if volume_raw is not None and volume_raw.strip():
            try:
                volume = parser.decimal_to_volume(volume_raw, label="volume")
            except parser.ImportError as exc:
                errors.append(str(exc))

        row: dict[str, Any] = {
            "row_index": index,
            "kind": "price_history",
            "date": date_value,
            "ticker": ticker,
            "close_q4": close_q4,
            "volume": volume,
            "errors": errors,
            "duplicate": False,
        }
        row["hash"] = dedupe.price_row_hash(row)

        if not errors and ticker and date_value:
            if row["hash"] in committed_hashes:
                row["duplicate"] = True
            elif any(
                existing["hash"] == row["hash"] and not existing["errors"] for existing in rows
            ):
                row["duplicate"] = True

        if not errors:
            row["effect"] = {
                "action": "price",
                "ticker": ticker,
                "date": date_value,
                "close_q4": close_q4,
                "volume": volume,
            }
        rows.append(row)

    return {"rows": rows}


def build_preview(kind: str, parsed: parser.CsvFile, plan: dict[str, Any]) -> dict[str, Any]:
    rows = plan["rows"]
    error_rows = [
        {"row_index": row["row_index"], "errors": row["errors"]} for row in rows if row["errors"]
    ]
    duplicates = [
        {"row_index": row["row_index"], "hash": row["hash"]} for row in rows if row["duplicate"]
    ]
    would_post = [row["effect"] for row in rows if row.get("effect")]
    valid_rows = sum(1 for row in rows if not row["errors"] and not row["duplicate"])
    return {
        "kind": kind,
        "total_rows": len(parsed.rows),
        "valid_rows": valid_rows,
        "error_rows": error_rows,
        "duplicates": duplicates,
        "absent_holdings": plan.get("absent_holdings", []),
        "would_post": would_post,
    }


__all__ = [
    "build_positions_plan",
    "build_trades_plan",
    "build_price_history_plan",
    "build_preview",
    "resolve_effective_mapping",
    "TRADE_TYPES",
]
