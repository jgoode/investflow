"""ITER-23 L1 red tests — price-history importer core (AC-IMP1h, docs/03 §4 IMP row).

Pure import-core coverage: price-row plan normalization (ticker uppercase, ISO
date, close → q4 via Decimal, optional volume → integer), mapping resolution for
the ``price_history`` kind with the repointed *bank statement* starter template,
and the price-row dedupe hash (import_rows registry). No floats — Decimal-only
conversion per NFR-10.
"""

from __future__ import annotations

import pytest

from app.services.importer import dedupe, evaluator, mapping, parser

PRICE_CSV = """Date,Ticker,Close,Volume
2024-01-02,msft,372.50,24850000
2024-01-03,MSFT,374.20,23100000
2024-01-04,MSFT,376.10,
2024-01-05,MSFT,378.85,20540000
"""

PRICE_COLUMNS = {"date": "Date", "ticker": "Ticker", "close": "Close", "volume": "Volume"}


# --- mapping.py: price_history kind + repointed bank statement starter ----------


def test_bank_statement_starter_is_price_history_shaped() -> None:
    template = next(
        entry for entry in mapping.list_starter_templates() if entry["name"] == "bank statement"
    )
    assert template["kind"] == "price_history"
    assert template["column_mapping"] == {
        "date": "Date",
        "ticker": "Ticker",
        "close": "Close",
        "volume": "Volume",
    }


def test_price_history_canonical_fields_carry_optional_volume() -> None:
    assert mapping.CANONICAL_FIELDS["price_history"] == ["date", "ticker", "close", "volume"]
    assert mapping.REQUIRED_FIELDS["price_history"] == ["date", "ticker", "close"]


def test_resolve_mapping_price_history_requires_date_ticker_close() -> None:
    resolved = mapping.resolve_mapping("price_history", dict(PRICE_COLUMNS))
    assert resolved == dict(PRICE_COLUMNS)

    with pytest.raises(mapping.ImportError, match="close"):
        mapping.resolve_mapping("price_history", {"date": "Date", "ticker": "Ticker"})


def test_resolve_mapping_price_history_rejects_unknown_fields() -> None:
    with pytest.raises(mapping.ImportError, match="description"):
        mapping.resolve_mapping(
            "price_history",
            {"date": "Date", "ticker": "Ticker", "close": "Close", "description": "Description"},
        )


def test_price_history_auto_detects_bank_statement_headers() -> None:
    detected = mapping.auto_detect_mapping("price_history", ["Date", "Ticker", "Close", "Volume"])
    assert detected == dict(PRICE_COLUMNS)


# --- parser.py: integer volume conversion ---------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [("24850000", 24_850_000), ("0", 0), (" 1234 ", 1234)],
)
def test_decimal_to_volume_converts_integers(value: str, expected: int) -> None:
    assert parser.decimal_to_volume(value) == expected


@pytest.mark.parametrize("value", ["1.5", "-3", "abc", ""])
def test_decimal_to_volume_rejects_non_integers(value: str) -> None:
    with pytest.raises(parser.ImportError):
        parser.decimal_to_volume(value)


# --- evaluator.py: price-history plan -------------------------------------------


def test_build_price_history_plan_normalizes_rows() -> None:
    parsed = parser.parse_csv(PRICE_CSV)
    plan = evaluator.build_price_history_plan(
        conn=None, parsed=parsed, column_mapping=PRICE_COLUMNS, committed_hashes=set()
    )
    rows = plan["rows"]
    assert [row["ticker"] for row in rows] == ["MSFT", "MSFT", "MSFT", "MSFT"]
    assert [row["date"] for row in rows] == [
        "2024-01-02",
        "2024-01-03",
        "2024-01-04",
        "2024-01-05",
    ]
    assert rows[0]["close_q4"] == 3_725_000  # 372.50 → q4
    assert rows[0]["volume"] == 24_850_000
    assert rows[2]["volume"] == 0  # blank volume allowed → 0
    assert rows[3]["close_q4"] == 3_788_500
    assert all(not row["errors"] for row in rows)
    assert rows[0]["effect"] == {
        "action": "price",
        "ticker": "MSFT",
        "date": "2024-01-02",
        "close_q4": 3_725_000,
        "volume": 24_850_000,
    }


def test_build_price_history_plan_reports_row_errors() -> None:
    text = """Date,Ticker,Close
2024-13-01,MSFT,372.50
2024-01-03,MSFT,374.20005
2024-01-04,,376.10
"""
    parsed = parser.parse_csv(text)
    plan = evaluator.build_price_history_plan(
        conn=None, parsed=parsed, column_mapping=PRICE_COLUMNS, committed_hashes=set()
    )
    errors = [row["errors"] for row in plan["rows"]]
    assert any("ISO" in message for message in errors[0])
    assert any("4 decimals" in message for message in errors[1])
    assert any("ticker is required" in message for message in errors[2])


def test_build_price_history_plan_requires_mapped_close_column() -> None:
    parsed = parser.parse_csv("Date,Ticker\n2024-01-02,MSFT\n")
    plan = evaluator.build_price_history_plan(
        conn=None,
        parsed=parsed,
        column_mapping={"date": "Date", "ticker": "Ticker", "close": None, "volume": None},
        committed_hashes=set(),
    )
    assert any("close column is not mapped" in message for message in plan["rows"][0]["errors"])


def test_build_price_history_plan_marks_committed_and_in_file_duplicates() -> None:
    parsed = parser.parse_csv(PRICE_CSV)
    first = evaluator.build_price_history_plan(
        conn=None, parsed=parsed, column_mapping=PRICE_COLUMNS, committed_hashes=set()
    )
    committed = {row["hash"] for row in first["rows"][:1]}  # first row already imported

    rerun = evaluator.build_price_history_plan(
        conn=None, parsed=parsed, column_mapping=PRICE_COLUMNS, committed_hashes=committed
    )
    assert rerun["rows"][0]["duplicate"] is True
    assert all(row["duplicate"] is False for row in rerun["rows"][1:])

    # identical row repeated inside one file → the later row is a duplicate
    repeated = parser.parse_csv(
        "Date,Ticker,Close,Volume\n2024-01-02,MSFT,372.50,100\n2024-01-02,MSFT,372.50,100\n"
    )
    dup_plan = evaluator.build_price_history_plan(
        conn=None, parsed=repeated, column_mapping=PRICE_COLUMNS, committed_hashes=set()
    )
    assert dup_plan["rows"][0]["duplicate"] is False
    assert dup_plan["rows"][1]["duplicate"] is True


# --- dedupe.py: price-row hash ---------------------------------------------------


def test_price_row_hash_is_deterministic_and_content_sensitive() -> None:
    row = {"date": "2024-01-02", "ticker": "MSFT", "close_q4": 3_725_000, "volume": 100}
    assert dedupe.price_row_hash(row) == dedupe.price_row_hash(dict(row))
    assert dedupe.price_row_hash(row) != dedupe.price_row_hash(dict(row, close_q4=3_725_001))
    assert dedupe.price_row_hash(row) != dedupe.price_row_hash(dict(row, date="2024-01-03"))
    # volume is part of the identity
    assert dedupe.price_row_hash(row) != dedupe.price_row_hash(dict(row, volume=101))
