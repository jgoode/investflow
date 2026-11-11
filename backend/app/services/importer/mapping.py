"""Column-mapping resolution + shipped starter templates (AC-IMP1a).

Canonical field names per import kind. The wizard sends a provided mapping
(canonical → CSV header title); when it is absent the importer auto-detects by
matching the starter template's suggested column titles against the CSV header.
"""

from __future__ import annotations

from typing import Any

from app.services.importer.parser import ImportError

CANONICAL_FIELDS: dict[str, list[str]] = {
    "positions": ["account", "ticker", "quantity", "avg_cost"],
    "trades": ["date", "type", "ticker", "quantity", "price", "fee", "amount", "cash_account"],
    "price_history": ["date", "ticker", "close", "volume"],
}

REQUIRED_FIELDS: dict[str, list[str]] = {
    "positions": ["account", "ticker", "quantity"],
    "trades": ["date", "type", "ticker"],
    "price_history": ["date", "ticker", "close"],
}

STARTER_TEMPLATES: list[dict[str, Any]] = [
    {
        "name": "positions snapshot",
        "kind": "positions",
        "column_mapping": {
            "account": "Account",
            "ticker": "Ticker",
            "quantity": "Quantity",
            "avg_cost": "Avg Cost",
        },
    },
    {
        "name": "trade history",
        "kind": "trades",
        "column_mapping": {
            "date": "Trade Date",
            "type": "Side",
            "ticker": "Symbol",
            "quantity": "Units",
            "price": "Trade Price",
            "fee": "Fee",
            "amount": "Amount",
            "cash_account": "Cash Account",
        },
    },
    {
        "name": "bank statement",
        "kind": "price_history",
        "column_mapping": {
            "date": "Date",
            "ticker": "Ticker",
            "close": "Close",
            "volume": "Volume",
        },
    },
]


def list_starter_templates() -> list[dict[str, Any]]:
    return [dict(template) for template in STARTER_TEMPLATES]


def resolve_mapping(kind: str, provided: dict[str, str] | None) -> dict[str, str | None]:
    if kind not in CANONICAL_FIELDS:
        raise ImportError(f"unsupported import kind: {kind!r}")

    resolved: dict[str, str | None] = {field: None for field in CANONICAL_FIELDS[kind]}
    if provided:
        for field, column in provided.items():
            if field in resolved:
                resolved[field] = str(column).strip() or None
            else:
                raise ImportError(f"unknown column field for {kind} import: {field!r}")

    missing = [field for field in REQUIRED_FIELDS[kind] if resolved.get(field) is None]
    if missing:
        raise ImportError(
            f"column mapping is missing required fields for {kind} import: {', '.join(missing)}"
        )
    return resolved


def auto_detect_mapping(kind: str, header_cells: list[str]) -> dict[str, str] | None:
    """Best-effort mapping from the starter template's suggested column titles."""
    header_by_key = {str(cell).strip().casefold(): cell.strip() for cell in header_cells}
    if not header_by_key:
        return None
    for template in STARTER_TEMPLATES:
        if template["kind"] != kind:
            continue
        detected: dict[str, str] = {}
        for field, suggested in template["column_mapping"].items():
            if suggested.casefold() in header_by_key:
                detected[field] = header_by_key[suggested.casefold()]
        missing = [field for field in REQUIRED_FIELDS[kind] if field not in detected]
        if not missing:
            return detected
    return None


def resolve_effective_mapping(
    kind: str, provided: dict[str, str] | None, header_cells: list[str]
) -> dict[str, str | None]:
    """User-provided mapping, with unmapped fields auto-detected from the header.

    A partial user mapping (e.g. a cash-event-only trade sheet) still picks up
    quantity/price/fee columns when the CSV carries the starter template's
    suggested titles, so optional columns keep working without re-mapping.
    """
    if kind not in CANONICAL_FIELDS:
        raise ImportError(f"unsupported import kind: {kind!r}")
    resolved: dict[str, str | None] = {field: None for field in CANONICAL_FIELDS[kind]}
    if provided:
        for field, column in provided.items():
            if field in resolved:
                resolved[field] = str(column).strip() or None
            else:
                raise ImportError(f"unknown column field for {kind} import: {field!r}")
    detected = auto_detect_mapping(kind, header_cells) or {}
    for field, column in detected.items():
        if resolved.get(field) is None:
            resolved[field] = column
    missing = [field for field in REQUIRED_FIELDS[kind] if resolved.get(field) is None]
    if missing:
        raise ImportError(
            f"column mapping is missing required fields for {kind} import: {', '.join(missing)}"
        )
    return resolved
