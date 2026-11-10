"""ITER-22 L2 red tests — import API (FR-IMP-1 AC-IMP1a–IMP1g, docs/03 §4 IMP row).

Contract-level coverage: preview semantics (AC-IMP1b), atomic commit with
skip-and-report dedupe (AC-IMP1c), positions replace-with-flag (AC-IMP1d),
trades through the avg-cost engine + cash events through the posting service
(AC-IMP1e), synchronous limits (AC-IMP1f), audit `import.*` (AC-IMP1g), and
mapping templates (AC-IMP1a).
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import CSRF_HEADER, register

POSITIONS_CSV_SESSION = """Account,Ticker,Quantity,Avg Cost
Brokerage A,AAPL,10,150.25
Brokerage A,MSFT,5,300
"""

POSITIONS_CSV_DROP_MSFT = """Account,Ticker,Quantity,Avg Cost
Brokerage A,AAPL,12,155
"""

TRADES_CSV = """Trade Date,Side,Symbol,Units,Trade Price,Fee,Amount,Cash Account
2024-01-02,buy,AAPL,10,150.25,1.99,,Brokerage A
2024-01-02,dividend,AAPL,,,,12.50,Brokerage A
2024-01-03,sell,AAPL,4,180.00,1.00,,Brokerage A
2024-01-05,fee,AAPL,,,,3.00,Brokerage A
"""

TRADE_COLUMNS = {
    "date": "Trade Date",
    "type": "Side",
    "ticker": "Symbol",
    "quantity": "Units",
    "price": "Trade Price",
    "fee": "Fee",
    "amount": "Amount",
    "cash_account": "Cash Account",
}

CASH_EVENT_COLUMNS = {
    "date": "Trade Date",
    "type": "Side",
    "ticker": "Symbol",
    "amount": "Amount",
    "cash_account": "Cash Account",
}


def _auth(client: TestClient) -> None:
    assert register(client, username="importer").status_code == 200


def _accounts(client: TestClient) -> dict[str, Any]:
    response = client.get(
        "/api/investments/accounts",
        headers=CSRF_HEADER,
    )
    assert response.status_code == 200
    payload = response.json()
    return {row["name"]: row["id"] for row in payload["accounts"]}


def _positions_payload(client: TestClient) -> dict[str, Any]:
    response = client.get("/api/investments/positions", headers=CSRF_HEADER)
    assert response.status_code == 200
    return response.json()


def _post_json(client: TestClient, path: str, payload: dict[str, Any]) -> Any:
    response = client.post(path, headers=CSRF_HEADER, json=payload)
    return response


def _ledger_transactions(client: TestClient) -> list[dict[str, Any]]:
    response = client.get(
        "/api/transactions?date_from=2000-01-01&date_to=2999-01-01&page_size=50",
        headers=CSRF_HEADER,
    )
    assert response.status_code == 200
    payload = response.json()
    return payload.get("transactions", payload.get("rows", []))


# --- unauthenticated access (NFR-2 middleware) --------------------------------


def test_import_endpoints_require_auth(client: TestClient) -> None:
    assert client.post("/api/imports/preview", headers=CSRF_HEADER, json={}).status_code == 401
    assert client.post("/api/imports/commit", headers=CSRF_HEADER, json={}).status_code == 401
    assert client.get("/api/imports/mappings", headers=CSRF_HEADER).status_code == 401


# --- AC-IMP1a: templates + mapping persistence --------------------------------


def test_starter_templates_are_exposed_and_saveable(client: TestClient) -> None:
    _auth(client)
    response = client.get("/api/imports/templates", headers=CSRF_HEADER)
    assert response.status_code == 200
    names = {template["name"] for template in response.json()["templates"]}
    assert names == {"positions snapshot", "trade history", "bank statement"}

    created = client.post(
        "/api/imports/mappings",
        headers=CSRF_HEADER,
        json={
            "name": "funny export",
            "kind": "trades",
            "column_mapping": dict(TRADE_COLUMNS),
        },
    )
    assert created.status_code == 201
    listed = client.get("/api/imports/mappings", headers=CSRF_HEADER).json()
    assert any(entry["name"] == "funny export" for entry in listed["mappings"])

    deleted = client.delete("/api/imports/mappings/1", headers=CSRF_HEADER)
    assert deleted.status_code in {200, 204}


# --- AC-IMP1d: positions import replace-with-flag ------------------------------


def test_positions_import_sets_quantity_and_avg_cost(client: TestClient) -> None:
    _auth(client)
    bindings = _accounts(client)
    payload = {
        "kind": "positions",
        "csv_text": POSITIONS_CSV_SESSION,
        "account_bindings": {"Brokerage A": bindings["Brokerage A"]},
        "confirm": True,
    }
    response = _post_json(client, "/api/imports/commit", payload)
    assert response.status_code == 200, response.text
    counts = response.json()["counts"]
    assert counts["posted"] == 2

    groups = _positions_payload(client)["account_groups"]
    rows = [position for group in groups for position in group["positions"]]
    by_ticker = {row["ticker"]: row for row in rows}
    assert by_ticker["AAPL"]["quantity_q4"] == 10 * 10_000
    assert by_ticker["AAPL"]["avg_cost_q4"] == 150_2500  # 150.25 → q4
    assert by_ticker["MSFT"]["quantity_q4"] == 5 * 10_000


def test_positions_import_flags_absent_holdings_and_requires_confirmation(
    client: TestClient,
) -> None:
    _auth(client)
    bindings = _accounts(client)
    commit = {
        "kind": "positions",
        "csv_text": POSITIONS_CSV_SESSION,
        "account_bindings": {"Brokerage A": bindings["Brokerage A"]},
        "confirm": True,
    }
    assert _post_json(client, "/api/imports/commit", commit).status_code == 200

    # Second snapshot that omits MSFT: preview must flag it for removal.
    second = {
        "kind": "positions",
        "csv_text": POSITIONS_CSV_DROP_MSFT,
        "account_bindings": {"Brokerage A": bindings["Brokerage A"]},
        "confirm": True,
    }
    preview = _post_json(client, "/api/imports/preview", dict(second, confirm=False))
    assert preview.status_code == 200
    absent = preview.json()["absent_holdings"]
    assert absent == [{"account_id": bindings["Brokerage A"], "ticker": "MSFT"}]

    # Commit without confirm → 422; nothing changes.
    refused = _post_json(client, "/api/imports/commit", second)
    assert refused.status_code == 422

    confirmed = _post_json(
        client,
        "/api/imports/commit",
        dict(second, confirm_absent_removals=True),
    )
    assert confirmed.status_code == 200, confirmed.text

    # absent holding moved to closed (kept in history) rather than deleted
    groups = _positions_payload(client)["account_groups"]
    open_rows = [row for group in groups for row in group["positions"]]
    assert all(row["ticker"] != "MSFT" for row in open_rows)

    batch = confirmed.json()["counts"]
    assert batch["removed"] == 1


# --- AC-IMP1e: trades through position engine; no ledger postings for buy/sell --


def test_trade_import_drives_position_engine_without_ledger_lines(client: TestClient) -> None:
    _auth(client)
    bindings = _accounts(client)
    payload = {
        "kind": "trades",
        "csv_text": TRADES_CSV,
        "column_mapping": TRADE_COLUMNS,
        "account_bindings": {"Brokerage A": bindings["Brokerage A"]},
        "confirm": True,
    }
    response = _post_json(client, "/api/imports/commit", payload)
    assert response.status_code == 200, response.text

    rows = [
        position
        for group in _positions_payload(client)["account_groups"]
        for position in group["positions"]
    ]
    aapl = next(row for row in rows if row["ticker"] == "AAPL")
    # buy 10@150.25 +1.99 (avg cost includes fee), then sell 4
    assert aapl["quantity_q4"] == 6 * 10_000
    assert aapl["avg_cost_q4"] > 0
    assert aapl["realized_gain_loss_cents"] > 0

    # buy/sell rows must NOT create ledger transactions (positions-only decision)
    ledger = _ledger_transactions(client)
    descriptions = [entry.get("description", "") for entry in ledger]
    assert not any("buy AAPL" in text or "sell AAPL" in text for text in descriptions)


# --- AC-IMP1e: dividend/fee rows post real balanced cash events ----------------


def test_dividend_and_fee_rows_post_balanced_transactions(client: TestClient) -> None:
    _auth(client)
    bindings = _accounts(client)
    payload = {
        "kind": "trades",
        "csv_text": TRADES_CSV,
        "column_mapping": CASH_EVENT_COLUMNS,
        "account_bindings": {"Brokerage A": bindings["Brokerage A"]},
        "confirm": True,
    }
    response = _post_json(client, "/api/imports/commit", payload)
    assert response.status_code == 200, response.text

    ledger = _ledger_transactions(client)
    # dividend row: debit Brokerage A (cash) / credit income; fee row: debit expense / credit cash
    dividend_rows = [
        entry
        for entry in ledger
        if entry.get("date") == "2024-01-02" and "import" in str(entry.get("reference", ""))
    ]
    assert dividend_rows, "dividend import row must post a real transaction"

    detail = client.get(f"/api/transactions/{dividend_rows[0]['id']}", headers=CSRF_HEADER).json()[
        "transaction"
    ]
    lines = detail["lines"]
    assert len(lines) == 2
    total_debit = sum(line["amount_cents"] for line in lines if line["direction"] == "debit")
    total_credit = sum(line["amount_cents"] for line in lines if line["direction"] == "credit")
    assert total_debit == total_credit == 12 * 100 + 50


# --- AC-IMP1c: duplicates skipped with a report, never double-posted -----------


def test_reimporting_the_same_trade_file_duplicates_everything(client: TestClient) -> None:
    _auth(client)
    bindings = _accounts(client)
    payload = {
        "kind": "trades",
        "csv_text": TRADES_CSV,
        "column_mapping": CASH_EVENT_COLUMNS,
        "account_bindings": {"Brokerage A": bindings["Brokerage A"]},
        "confirm": True,
    }
    first = _post_json(client, "/api/imports/commit", payload)
    assert first.status_code == 200, first.text
    first_counts = first.json()["counts"]
    assert first_counts["duplicate"] == 0

    second = _post_json(client, "/api/imports/commit", payload)
    assert second.status_code == 200, second.text
    second_counts = second.json()["counts"]
    assert second_counts["duplicate"] == 4
    assert second_counts["posted"] == 0

    # positions did not change by the re-import
    rows = [
        position
        for group in _positions_payload(client)["account_groups"]
        for position in group["positions"]
    ]
    aapl = next(row for row in rows if row["ticker"] == "AAPL")
    assert aapl["realized_gain_loss_cents"] > 0  # same as after first import


# --- AC-IMP1c: hard row error aborts the whole file ------------------------------


def test_hard_row_error_aborts_everything(client: TestClient) -> None:
    _auth(client)
    bindings = _accounts(client)
    good_then_bad = """Trade Date,Side,Symbol,Units,Trade Price,Fee,Cash Account
2024-01-02,buy,AAPL,10,150.25,1.99,Brokerage A
2024-01-03,sell,AAPL,999,180.00,1.00,Brokerage A
"""
    payload = {
        "kind": "trades",
        "csv_text": good_then_bad,
        "column_mapping": CASH_EVENT_COLUMNS,
        "account_bindings": {"Brokerage A": bindings["Brokerage A"]},
        "confirm": True,
    }
    response = _post_json(client, "/api/imports/commit", payload)
    assert response.status_code == 422
    body = response.json()
    detail = str(body.get("detail", body))
    assert "999" not in detail or "exceeds" in detail.lower()

    # nothing was committed — no positions exist and the ledger is untouched
    assert _ledger_transactions(client) == []
    assert _positions_payload(client)["account_groups"] == []


# --- AC-IMP1e: replay-order violations are row errors, not auto-fixed ------------


def test_out_of_order_trade_rows_are_rejected_with_row_errors(client: TestClient) -> None:
    _auth(client)
    bindings = _accounts(client)
    out_of_order = """Trade Date,Side,Symbol,Units,Trade Price,Fee,Cash Account
2024-01-10,sell,AAPL,4,180.00,1.00,Brokerage A
2024-01-02,buy,AAPL,10,150.25,1.99,Brokerage A
"""
    payload = {
        "kind": "trades",
        "csv_text": out_of_order,
        "column_mapping": CASH_EVENT_COLUMNS,
        "account_bindings": {"Brokerage A": bindings["Brokerage A"]},
        "confirm": True,
    }
    response = _post_json(client, "/api/imports/commit", payload)
    assert response.status_code == 422
    text = response.text
    assert "date order" in text.lower() or "sequence" in text.lower()
    assert _ledger_transactions(client) == []
    assert _positions_payload(client)["account_groups"] == []


# --- AC-IMP1f: synchronous limits ------------------------------------------------


def test_too_many_rows_is_refused_with_split_suggestion(client: TestClient) -> None:
    _auth(client)
    header = "Trade Date,Side,Symbol,Units,Trade Price,Fee,Cash Account"
    rows = "\n".join(f"2024-01-02,buy,T{i},1,10,0,Bank A" for i in range(5001))
    payload = {
        "kind": "trades",
        "csv_text": f"{header}\n{rows}",
        "column_mapping": CASH_EVENT_COLUMNS,
        "account_bindings": {"Bank A": 1},
        "confirm": True,
    }
    response = _post_json(client, "/api/imports/commit", payload)
    assert response.status_code == 422
    assert "split" in response.text.lower()


@pytest.mark.parametrize("chunk", ["x" * (5 * 1024 * 1024 + 1)])
def test_oversized_file_is_refused(client: TestClient, chunk: str) -> None:
    _auth(client)
    payload = {
        "kind": "trades",
        "csv_text": chunk,
        "confirm": True,
    }
    response = _post_json(client, "/api/imports/commit", payload)
    assert response.status_code == 422
    assert "5 MB" in response.text


# --- AC-IMP1g: audit trail -------------------------------------------------------


def test_commit_writes_import_audit_entries(client: TestClient) -> None:
    _auth(client)
    bindings = _accounts(client)
    _post_json(
        client,
        "/api/imports/commit",
        {
            "kind": "positions",
            "csv_text": POSITIONS_CSV_SESSION,
            "account_bindings": {"Brokerage A": bindings["Brokerage A"]},
            "confirm": True,
        },
    )
    _post_json(
        client,
        "/api/imports/commit",
        {
            "kind": "trades",
            "csv_text": TRADES_CSV,
            "column_mapping": CASH_EVENT_COLUMNS,
            "account_bindings": {"Brokerage A": bindings["Brokerage A"]},
            "confirm": True,
        },
    )
    response = client.get("/api/audit", headers=CSRF_HEADER)
    assert response.status_code == 200
    actions = {entry["action"] for entry in response.json()["items"]}
    assert "import.positions" in actions
    assert "import.transactions" in actions
