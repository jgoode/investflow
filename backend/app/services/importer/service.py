"""Import commit orchestration (AC-IMP1c/1d/1e/1f/1g).

Atomicity: the whole file commits inside a single connection under
``BEGIN IMMEDIATE`` — position updates go through the avg-cost engine
(``positions.apply_trade_on_connection``), cash events (dividend/fee) go
through the existing posting service (``transactions.post_transaction_on_connection``).
Buy/sell rows never touch the ledger (ADR-008); the importer never writes
``transaction_lines`` directly.

Any row error, replay-order violation, or unconfirmed removal rolls the whole
file back — nothing is half-imported.
"""

from __future__ import annotations

import json
import time
from typing import Any

from fastapi import HTTPException, status

from app.db.connection import connect
from app.positions import apply_trade_on_connection, ensure_positions_tables
from app.providers import ensure_market_tables
from app.services.importer import dedupe, evaluator, mapping, parser
from app.services.importer.parser import ImportError as FileImportError
from app.transactions import (
    _log_audit,
    ensure_transactions_tables,
    post_transaction_on_connection,
)

KINDS = ("positions", "trades", "price_history")
AUDIT_ACTIONS = {
    "positions": "import.positions",
    "trades": "import.transactions",
    "price_history": "import.price_history",
}

DEFAULT_INCOME_ACCOUNT = "Interest & Dividends"
DEFAULT_EXPENSE_ACCOUNT = "Fees"

MAX_FILE_BYTES = parser.MAX_FILE_BYTES
MAX_ROWS = parser.MAX_ROWS


def _now_ts() -> int:
    return int(time.time())


def ensure_import_tables() -> None:
    """Mirror of migration 0007 (idempotent, for pre-migration callers/tests)."""
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS import_mappings (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                kind TEXT NOT NULL,
                columns_json TEXT NOT NULL,
                created_by INTEGER REFERENCES users(id),
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS import_batches (
                id INTEGER PRIMARY KEY,
                kind TEXT NOT NULL,
                file_name TEXT NOT NULL,
                status TEXT NOT NULL,
                counts_json TEXT NOT NULL,
                created_by INTEGER REFERENCES users(id),
                created_at INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_import_batches_kind ON import_batches(kind, status)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS import_rows (
                id INTEGER PRIMARY KEY,
                batch_id INTEGER NOT NULL REFERENCES import_batches(id) ON DELETE CASCADE,
                row_index INTEGER NOT NULL,
                row_hash TEXT NOT NULL,
                status TEXT NOT NULL,
                detail_json TEXT,
                created_at INTEGER NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS ix_import_rows_batch ON import_rows(batch_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_import_rows_hash ON import_rows(row_hash)")
        conn.commit()


def record_batch(
    conn: Any,
    *,
    kind: str,
    file_name: str,
    status: str,
    counts: dict[str, int],
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO import_batches (kind, file_name, status, counts_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (kind, file_name, status, json.dumps(counts), _now_ts()),
    )
    return int(cursor.lastrowid)


def record_row(
    conn: Any,
    *,
    batch_id: int,
    row_index: int,
    row_hash: str,
    status: str,
    detail: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO import_rows (batch_id, row_index, row_hash, status, detail_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (batch_id, row_index, row_hash, status, json.dumps(detail) if detail else None, _now_ts()),
    )


def select_imported_row_hashes(conn: Any, *, kind: str) -> set[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT r.row_hash
        FROM import_rows r
        JOIN import_batches b ON b.id = r.batch_id
        WHERE b.kind = ? AND b.status = 'committed'
        """,
        (kind,),
    ).fetchall()
    return {str(row["row_hash"]) for row in rows}


def _parse_bindings(raw: Any) -> dict[str, int]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="account_bindings must be an object of {csv account: account_id}",
        )
    bindings: dict[str, int] = {}
    for label, value in raw.items():
        try:
            bindings[str(label).strip()] = int(value)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"account binding for {label!r} must carry an integer account_id",
            ) from exc
    return bindings


def _parse_request(
    payload: dict[str, Any], *, require_confirm: bool
) -> tuple[str, parser.CsvFile, dict[str, str | None], dict[str, int], str, dict[str, Any]]:
    kind = str(payload.get("kind") or "").strip()
    if kind not in KINDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(f"unsupported import kind: {kind!r}; supported kinds: {', '.join(KINDS)}"),
        )
    csv_text = payload.get("csv_text")
    if not isinstance(csv_text, str):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="csv_text is required",
        )
    file_name = str(payload.get("file_name") or "portfolio.csv")
    bindings = _parse_bindings(payload.get("account_bindings"))
    if require_confirm and not payload.get("confirm"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="run the preview first and confirm the import (confirm=true)",
        )
    try:
        parsed = parser.parse_csv(csv_text)
    except FileImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    provided = payload.get("column_mapping")
    if provided is not None and not isinstance(provided, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="column_mapping must be an object of {field: csv column title}",
        )
    try:
        resolved = mapping.resolve_effective_mapping(kind, provided, parsed.header)
    except FileImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return kind, parsed, resolved, bindings, file_name, payload


def _default_account_id(conn: Any, name: str, *, flow: str) -> int:
    row = conn.execute(
        "SELECT id FROM accounts WHERE name = ? AND is_archived = 0 ORDER BY id LIMIT 1",
        (name,),
    ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"import requires the seeded {flow} account {name!r}; seed the COA first",
        )
    return int(row["id"])


def _post_cash_event(
    conn: Any,
    row: dict[str, Any],
    *,
    user_id: int | None,
) -> int:
    """Post a dividend/fee row as a real balanced two-leg transaction."""
    account_id = int(row["account_id"])
    amount_cents = int(row["amount_cents"] or 0)
    ticker = str(row["ticker"])
    memo = f"Dividend {ticker} (import)" if row["type"] == "dividend" else f"Fee {ticker}"
    if row["type"] == "dividend":
        counterpart_id = _default_account_id(conn, DEFAULT_INCOME_ACCOUNT, flow="income")
        lines = [
            {
                "account_id": account_id,
                "direction": "debit",
                "amount_cents": amount_cents,
                "memo": memo,
            },
            {
                "account_id": counterpart_id,
                "direction": "credit",
                "amount_cents": amount_cents,
                "memo": memo,
            },
        ]
    else:
        counterpart_id = _default_account_id(conn, DEFAULT_EXPENSE_ACCOUNT, flow="expense")
        lines = [
            {
                "account_id": counterpart_id,
                "direction": "debit",
                "amount_cents": amount_cents,
                "memo": memo,
            },
            {
                "account_id": account_id,
                "direction": "credit",
                "amount_cents": amount_cents,
                "memo": memo,
            },
        ]
    payload = {
        "date": row["date"],
        "description": memo,
        "reference": f"import:{dedupe.hash16(row['hash'])}",
        "lines": lines,
    }
    tx = post_transaction_on_connection(conn, payload, created_by=user_id)
    return int(tx["id"])


def _apply_positions_rows(conn: Any, rows: list[dict[str, Any]]) -> int:
    posted = 0
    for row in rows:
        if row["errors"] or row["duplicate"] or row["account_id"] is None:
            continue
        existing = conn.execute(
            "SELECT id FROM positions WHERE account_id = ? AND ticker = ?",
            (row["account_id"], row["ticker"]),
        ).fetchone()
        now = _now_ts()
        if existing is None:
            conn.execute(
                """
                INSERT INTO positions (
                    account_id, ticker, quantity_q4, avg_cost_q4, status,
                    realized_gain_loss_cents, last_price_q4, last_trade_date,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'open', 0, 0, '', ?, ?)
                """,
                (
                    row["account_id"],
                    row["ticker"],
                    row["quantity_q4"],
                    row["avg_cost_q4"],
                    now,
                    now,
                ),
            )
        else:
            conn.execute(
                """
                UPDATE positions
                SET quantity_q4 = ?, avg_cost_q4 = ?, status = 'open', updated_at = ?
                WHERE id = ?
                """,
                (row["quantity_q4"], row["avg_cost_q4"], now, int(existing["id"])),
            )
        posted += 1
    return posted


def _remove_absent_holdings(conn: Any, absent: list[dict[str, Any]]) -> int:
    removed = 0
    for entry in absent:
        cursor = conn.execute(
            """
            UPDATE positions
            SET quantity_q4 = 0, avg_cost_q4 = 0, status = 'closed', updated_at = ?
            WHERE account_id = ? AND ticker = ? AND status = 'open'
            """,
            (_now_ts(), entry["account_id"], entry["ticker"]),
        )
        removed += int(cursor.rowcount > 0)
    return removed


def _apply_price_rows(conn: Any, rows: list[dict[str, Any]]) -> int:
    """Upsert price_cache rows (source='manual') and refresh latest_quotes.

    price_cache's unique key is (ticker, date): a row is upserted, never
    duplicated. The newest imported close per ticker is promoted into
    latest_quotes with asof = the close date (midnight UTC) so the manual
    price carries its true date (AC-I2c: manual rows win over provider rows).
    No ledger postings — price history writes no transaction rows (02 §4.5).
    """
    posted = 0
    newest: dict[str, dict[str, Any]] = {}
    now = _now_ts()
    for row in rows:
        if row["errors"] or row["duplicate"]:
            continue
        ticker = str(row["ticker"])
        date_value = str(row["date"])
        conn.execute(
            """
            INSERT INTO price_cache (ticker, date, close_q4, volume, source, fetched_at)
            VALUES (?, ?, ?, ?, 'manual', ?)
            ON CONFLICT(ticker, date) DO UPDATE SET
                close_q4 = excluded.close_q4,
                volume = excluded.volume,
                source = 'manual',
                fetched_at = excluded.fetched_at
            """,
            (ticker, date_value, int(row["close_q4"] or 0), int(row["volume"] or 0), now),
        )
        current = newest.get(ticker)
        if current is None or date_value > current["date"]:
            newest[ticker] = {"date": date_value, "close_q4": int(row["close_q4"] or 0)}
        posted += 1

    for ticker, entry in newest.items():
        conn.execute(
            """
            INSERT INTO latest_quotes (ticker, price_q4, asof, source, fetched_at)
            VALUES (?, ?, ?, 'manual', ?)
            ON CONFLICT(ticker) DO UPDATE SET
                price_q4 = excluded.price_q4,
                asof = excluded.asof,
                source = excluded.source,
                fetched_at = excluded.fetched_at
            """,
            (ticker, entry["close_q4"], f"{entry['date']}T00:00:00Z", now),
        )
    return posted


def run_preview(payload: dict[str, Any], *, user_id: int | None = None) -> dict[str, Any]:
    kind, parsed, resolved, bindings, _file_name, _raw = _parse_request(
        payload, require_confirm=False
    )
    ensure_positions_tables()
    ensure_import_tables()
    with connect() as conn:
        if kind == "positions":
            plan = evaluator.build_positions_plan(
                conn, parsed=parsed, column_mapping=resolved, bindings=bindings
            )
        elif kind == "price_history":
            plan = evaluator.build_price_history_plan(
                conn,
                parsed=parsed,
                column_mapping=resolved,
                committed_hashes=select_imported_row_hashes(conn, kind=kind),
            )
        else:
            plan = evaluator.build_trades_plan(
                conn,
                parsed=parsed,
                column_mapping=resolved,
                bindings=bindings,
                committed_hashes=select_imported_row_hashes(conn, kind=kind),
            )
    return evaluator.build_preview(kind, parsed, plan)


def _reject_row_errors(rows: list[dict[str, Any]], order_errors: list[str]) -> None:
    row_errors = [
        {"row_index": row["row_index"], "errors": row["errors"]} for row in rows if row["errors"]
    ]
    if row_errors or order_errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "message": "import aborted: the file contains row errors; "
                "fix them and re-run the preview (nothing was committed)",
                "row_errors": row_errors,
                "order_errors": order_errors,
            },
        )


def run_commit(payload: dict[str, Any], *, user_id: int | None = None) -> dict[str, Any]:
    kind, parsed, resolved, bindings, file_name, raw_payload = _parse_request(
        payload, require_confirm=True
    )
    ensure_positions_tables()
    ensure_import_tables()
    # audit_log + transaction tables must exist before BEGIN IMMEDIATE, since
    # _log_audit joins this transaction instead of ensuring on its own conn.
    ensure_transactions_tables()
    # price_cache / latest_quotes must exist before BEGIN IMMEDIATE for the
    # price_history kind (ensure_* on their own connection would deadlock the
    # write lock mid-transaction).
    ensure_market_tables()

    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            if kind == "positions":
                plan = evaluator.build_positions_plan(
                    conn, parsed=parsed, column_mapping=resolved, bindings=bindings
                )
                absent = plan["absent_holdings"]
                if absent and not raw_payload.get("confirm_absent_removals"):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail={
                            "message": (
                                "import would close holdings absent from the snapshot; "
                                "re-run with confirm_absent_removals=true to accept: "
                                + ", ".join(
                                    f"account {item['account_id']} {item['ticker']}"
                                    for item in absent
                                )
                            ),
                            "absent_holdings": absent,
                        },
                    )
                rows = plan["rows"]
                order_errors: list[str] = []
            elif kind == "price_history":
                plan = evaluator.build_price_history_plan(
                    conn,
                    parsed=parsed,
                    column_mapping=resolved,
                    committed_hashes=select_imported_row_hashes(conn, kind=kind),
                )
                rows = plan["rows"]
                order_errors = []
            else:
                plan = evaluator.build_trades_plan(
                    conn,
                    parsed=parsed,
                    column_mapping=resolved,
                    bindings=bindings,
                    committed_hashes=select_imported_row_hashes(conn, kind=kind),
                )
                rows = plan["rows"]
                order_errors = dedupe.check_replay_order(rows)

            _reject_row_errors(rows, order_errors)

            counts = {"posted": 0, "duplicate": 0, "removed": 0}
            results: list[dict[str, Any]] = []
            registrations: list[tuple[int, str, str]] = []
            if kind == "positions":
                counts["posted"] = _apply_positions_rows(conn, rows)
                counts["removed"] = _remove_absent_holdings(conn, absent)
                for row in rows:
                    results.append({"row_index": row["row_index"], "status": "posted"})
                    registrations.append((row["row_index"], row["hash"], "posted"))
            elif kind == "price_history":
                counts["posted"] = _apply_price_rows(conn, rows)
                for row in rows:
                    status_ = "duplicate" if row["duplicate"] else "posted"
                    if row["duplicate"]:
                        counts["duplicate"] += 1
                    results.append({"row_index": row["row_index"], "status": status_})
                    registrations.append((row["row_index"], row["hash"], status_))
            else:
                for row in rows:
                    if row["duplicate"]:
                        counts["duplicate"] += 1
                        results.append({"row_index": row["row_index"], "status": "duplicate"})
                        registrations.append((row["row_index"], row["hash"], "duplicate"))
                        continue
                    if row["type"] in {"buy", "sell"}:
                        apply_trade_on_connection(
                            conn,
                            account_id=int(row["account_id"]),
                            ticker=row["ticker"],
                            side=row["type"],
                            quantity_q4=int(row["quantity_q4"] or 0),
                            price_q4=int(row["price_q4"] or 0),
                            fee_cents=int(row["fee_cents"] or 0),
                            trade_date=row["date"],
                        )
                    else:
                        _post_cash_event(conn, row, user_id=user_id)
                    counts["posted"] += 1
                    results.append({"row_index": row["row_index"], "status": "posted"})
                    registrations.append((row["row_index"], row["hash"], "posted"))

            batch_id = record_batch(
                conn,
                kind=kind,
                file_name=file_name,
                status="committed",
                counts=counts,
            )
            for row_index, row_hash, row_status in registrations:
                record_row(
                    conn,
                    batch_id=batch_id,
                    row_index=row_index,
                    row_hash=row_hash,
                    status=row_status,
                )
            _log_audit(
                action=AUDIT_ACTIONS[kind],
                summary=f"imported {kind} from {file_name}: {json.dumps(counts)}",
                entity="import_batches",
                entity_id=batch_id,
                user_id=user_id,
                conn=conn,
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    return {"counts": counts, "results": results}
