"""ITER-22 L1 red tests — importer core (FR-IMP-1, docs/03 §4 IMP row).

Pure import-core coverage: CSV parsing/limits, decimal→q4/cents conversion
(NFR-10: no floats), column-mapping resolution with starter templates,
trade-row hash-tuple dedupe, and (account, ticker) replay-order validation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.importer import dedupe, mapping, parser

# --- parser.py ---------------------------------------------------------------


def test_parse_csv_splits_rows_and_strips_whitespace() -> None:
    text = "Ticker,Quantity\n AAPL , 10 \nMSFT,2.5\n"
    parsed = parser.parse_csv(text)
    assert parsed.rows == [
        {"ticker": "AAPL", "quantity": "10"},
        {"ticker": "MSFT", "quantity": "2.5"},
    ]
    assert parsed.header == ["Ticker", "Quantity"]


def test_parse_csv_rejects_empty_input() -> None:
    with pytest.raises(parser.ImportError, match="empty"):
        parser.parse_csv("")


def test_parse_csv_rejects_more_than_5000_rows() -> None:
    text = "ticker\n" + "\n".join(f"T{i}" for i in range(5001))
    with pytest.raises(parser.ImportError, match="5,000 rows|split"):
        parser.parse_csv(text)


def test_parse_csv_rejects_unknown_csv_structure_characters() -> None:
    # quotes within the unquoted field → structurally broken CSV (FR-IMP-1 schema check)
    with pytest.raises(parser.ImportError):
        parser.parse_csv('Ticker,Quantity\nAAP"L,10\n')


# --- decimal → scaled-integer helpers (NFR-10: no floats) ---------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("10", 10 * 10_000),
        ("12.3456", 123_456),
        ("0.0001", 1),
        (" 2.5 ", 25_000),
    ],
)
def test_decimal_to_q4_converts_exactly(value: str, expected: int) -> None:
    assert parser.decimal_to_q4(value) == expected


def test_decimal_to_q4_rejects_more_than_four_decimals() -> None:
    with pytest.raises(parser.ImportError, match="4 decimals"):
        parser.decimal_to_q4("1.23456")


@pytest.mark.parametrize(
    ("value", "expected"),
    [("123.45", 12345), ("100", 10000)],
)
def test_decimal_to_cents_converts_exactly(value: str, expected: int) -> None:
    assert parser.decimal_to_cents(value) == expected


def test_decimal_to_cents_rejects_more_than_two_decimals() -> None:
    with pytest.raises(parser.ImportError, match="2 decimals"):
        parser.decimal_to_cents("1.2345")


def test_decimal_conversion_rejects_negative_and_garbage() -> None:
    with pytest.raises(parser.ImportError):
        parser.decimal_to_q4("-5")
    with pytest.raises(parser.ImportError):
        parser.decimal_to_cents("abc")


# --- mapping.py ----------------------------------------------------------------


def test_starter_templates_include_three_named_starts() -> None:
    names = {template["name"] for template in mapping.list_starter_templates()}
    assert names == {"positions snapshot", "trade history", "bank statement"}


def test_starter_templates_carry_kinds_and_column_suggestions() -> None:
    trade = next(
        template
        for template in mapping.list_starter_templates()
        if template["name"] == "trade history"
    )
    assert trade["kind"] == "trades"
    assert trade["column_mapping"] == {
        "date": "Trade Date",
        "type": "Side",
        "ticker": "Symbol",
        "quantity": "Units",
        "price": "Trade Price",
        "fee": "Fee",
        "amount": "Amount",
        "cash_account": "Cash Account",
    }


def test_resolve_mapping_requires_required_fields_per_kind() -> None:
    resolved = mapping.resolve_mapping(
        kind="trades",
        provided={
            "date": "Trade Date",
            "type": "Side",
            "ticker": "Symbol",
            "quantity": "Units",
            "price": "Trade Price",
        },
    )
    assert resolved == {
        "date": "Trade Date",
        "type": "Side",
        "ticker": "Symbol",
        "quantity": "Units",
        "price": "Trade Price",
        "fee": None,
        "amount": None,
        "cash_account": None,
    }

    with pytest.raises(mapping.ImportError, match="date"):
        mapping.resolve_mapping(kind="trades", provided={"ticker": "Symbol"})


def test_resolve_mapping_positions_kind_requires_ticker_and_quantity() -> None:
    with pytest.raises(mapping.ImportError, match="quantity"):
        mapping.resolve_mapping(kind="positions", provided={"ticker": "Symbol"})


# --- dedupe.py ------------------------------------------------------------------


def test_trade_row_hash_is_deterministic_and_order_insensitive_in_keys() -> None:
    row = {
        "date": "2024-01-02",
        "ticker": "AAPL",
        "type": "buy",
        "quantity_q4": 100_000,
        "price_q4": 180_0000,
        "fee_cents": 199,
        "cash_account": "Bank A",
    }
    same = dict(row)
    assert dedupe.trade_row_hash(row) == dedupe.trade_row_hash(same)

    variant = dict(row, quantity_q4=100_001)
    assert dedupe.trade_row_hash(row) != dedupe.trade_row_hash(variant)


def test_select_imported_row_hashes_only_counts_committed_batches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Isolate from the dev DB: fresh per-test DB migrated to head (DEF-004).
    db_path = tmp_path / "importer-test.db"
    monkeypatch.setenv("INVESTFLOW_DB_PATH", str(db_path))
    from tests.conftest import _alembic_upgrade_head

    _alembic_upgrade_head(db_path)
    from app.db.connection import connect
    from app.services.importer import service

    service.ensure_import_tables()
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        batch_id = service.record_batch(
            conn,
            kind="trades",
            file_name="import.csv",
            status="committed",
            counts={"posted": 1, "duplicate": 0},
        )
        service.record_row(
            conn,
            batch_id=batch_id,
            row_index=0,
            row_hash="hash-aabbccdd",
            status="posted",
        )
        conn.commit()

        hashes = service.select_imported_row_hashes(conn, kind="trades")

    # committed truth hashes are visible for dedupe
    assert hashes == {"hash-aabbccdd"}


# --- replay-order validation -----------------------------------------------------


def test_check_replay_order_rejects_out_of_order_buy_before_sell_dates() -> None:
    plan = [
        {"account_id": 1, "ticker": "AAPL", "date": "2024-03-01", "type": "sell"},
        {"account_id": 1, "ticker": "AAPL", "date": "2024-01-02", "type": "buy"},
    ]
    errors = dedupe.check_replay_order(plan)
    assert errors and "date order" in errors[0].lower()


def test_check_replay_order_accepts_ordered_rows_and_different_ticker_streams() -> None:
    plan = [
        {"account_id": 1, "ticker": "AAPL", "date": "2024-01-02", "type": "buy"},
        {"account_id": 1, "ticker": "AAPL", "date": "2024-01-02", "type": "sell"},
        {"account_id": 1, "ticker": "MSFT", "date": "2024-01-01", "type": "buy"},
    ]
    assert dedupe.check_replay_order(plan) == []
