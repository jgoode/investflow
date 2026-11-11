"""Trade-row hash-tuple dedupe + replay-order validation (AC-IMP1c/AC-IMP1e).

The hash tuple covers the normalized plan fields of a trade row (date, side,
ticker, scaled quantity/price/fee, cash amount, resolved account ids) so the
same file re-imported produces the same hashes → duplicates skipped with a
report, never double-posted.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

_HASHED_FIELDS = (
    "date",
    "type",
    "ticker",
    "quantity_q4",
    "price_q4",
    "fee_cents",
    "amount_cents",
    "account_id",
    "cash_account_id",
)


def trade_row_hash(row: dict[str, Any]) -> str:
    """Deterministic content hash over the normalized plan fields of a row."""
    fields = {field: row.get(field) for field in _HASHED_FIELDS}
    payload = json.dumps(fields, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


_PRICE_HASHED_FIELDS = ("date", "ticker", "close_q4", "volume")


def price_row_hash(row: dict[str, Any]) -> str:
    """Deterministic content hash over a price-history plan row.

    Identity is (date, ticker, close, volume); a corrected close for the same
    (ticker, date) hashes differently → it re-posts and upserts the cached row
    instead of being skipped as a duplicate.
    """
    fields = {field: row.get(field) for field in _PRICE_HASHED_FIELDS}
    payload = json.dumps(fields, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def hash16(row_hash: str) -> str:
    """Short hash used inside the transaction reference (``import:<hash16>``)."""
    return row_hash[:16]


def check_replay_order(rows: list[dict[str, Any]]) -> list[str]:
    """(account, ticker) streams must replay in non-decreasing date order.

    Sells before buys are never auto-fixed; a violation is a hard row error.
    Rows without an account/ticker/date (already error rows) are ignored here —
    they fail through their own errors.
    """
    errors: list[str] = []
    last_seen: dict[tuple[Any, str], tuple[str, int]] = {}
    for row in rows:
        account_id = row.get("account_id")
        ticker = row.get("ticker")
        row_date = row.get("date")
        if not account_id or not ticker or not row_date:
            continue
        key = (account_id, str(ticker))
        previous = last_seen.get(key)
        if previous is not None and str(row_date) < previous[0]:
            errors.append(
                f"row {row.get('row_index')}: date order violation for {ticker}: "
                f"{row_date} precedes row {previous[1]} dated {previous[0]} "
                "(sells before buys are never reordered)"
            )
            continue
        last_seen[key] = (str(row_date), int(row.get("row_index") or 0))
    return errors
