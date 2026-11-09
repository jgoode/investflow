from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import CSRF_HEADER, register


def _find_account_by_name(tree: list[dict], name: str) -> dict:
    for row in tree:
        if row.get("name") == name:
            return row
        children = row.get("children") or []
        found = _find_account_by_name(children, name)
        if found is not None:
            return found
    return None


def _brokerage_account_id(client: TestClient) -> int:
    response = client.get("/api/accounts/tree", headers=CSRF_HEADER)
    assert response.status_code == 200, response.text
    brokerage = _find_account_by_name(response.json()["tree"], "Brokerage A")
    assert brokerage is not None, "Brokerage A missing from seeded account tree"
    return int(brokerage["id"])


def test_manual_positions_buy_sell_and_grouping(client: TestClient) -> None:
    register(client, "alice")
    brokerage_id = _brokerage_account_id(client)

    buy = client.post(
        "/api/investments/trades",
        headers=CSRF_HEADER,
        json={
            "account_id": brokerage_id,
            "ticker": "AAPL",
            "side": "buy",
            "quantity_q4": 2_0000,
            "price_q4": 1_505_000,
            "fee_cents": 125,
            "trade_date": "2026-11-09",
        },
    )
    assert buy.status_code == 200, buy.text
    position = buy.json()["position"]
    assert position["ticker"] == "AAPL"
    assert position["quantity_q4"] == 2_0000
    assert position["avg_cost_q4"] == 1_511_250

    second = client.post(
        "/api/investments/trades",
        headers=CSRF_HEADER,
        json={
            "account_id": brokerage_id,
            "ticker": "AAPL",
            "side": "buy",
            "quantity_q4": 3_0000,
            "price_q4": 1_600_000,
            "fee_cents": 150,
            "trade_date": "2026-11-10",
        },
    )
    assert second.status_code == 200, second.text
    assert second.json()["position"]["avg_cost_q4"] == 1_567_500

    sell = client.post(
        "/api/investments/trades",
        headers=CSRF_HEADER,
        json={
            "account_id": brokerage_id,
            "ticker": "AAPL",
            "side": "sell",
            "quantity_q4": 1_0000,
            "price_q4": 1_732_500,
            "fee_cents": 0,
            "trade_date": "2026-11-11",
        },
    )
    assert sell.status_code == 200, sell.text
    assert sell.json()["realized_gain_loss_cents"] == 1_650

    response = client.get("/api/investments/positions", headers=CSRF_HEADER)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["overall_total_market_value_cents"] >= 0
    assert payload["account_groups"][0]["account_name"] == "Brokerage A"
    assert payload["account_groups"][0]["positions"][0]["ticker"] == "AAPL"

    extra_account = client.post(
        "/api/accounts",
        headers=CSRF_HEADER,
        json={
            "code": "BROKERAGE-B",
            "name": "Brokerage B",
            "type": "asset",
            "subtype": "brokerage",
            "parent_id": _find_account_by_name(
                client.get("/api/accounts/tree", headers=CSRF_HEADER).json()["tree"],
                "Investments",
            )["id"],
            "is_investment": True,
        },
    )
    assert extra_account.status_code == 200, extra_account.text

    second_buy = client.post(
        "/api/investments/trades",
        headers=CSRF_HEADER,
        json={
            "account_id": extra_account.json()["account"]["id"],
            "ticker": "MSFT",
            "side": "buy",
            "quantity_q4": 2_0000,
            "price_q4": 300_000,
            "fee_cents": 200,
            "trade_date": "2026-11-12",
        },
    )
    assert second_buy.status_code == 200, second_buy.text

    grouped = client.get("/api/investments/positions", headers=CSRF_HEADER)
    assert grouped.status_code == 200, grouped.text
    groups = grouped.json()["account_groups"]
    assert len(groups) >= 2
    assert groups[0]["account_name"] in {"Brokerage A", "Brokerage B"}


def test_oversell_is_rejected_with_422(client: TestClient) -> None:
    register(client, "alice")
    brokerage_id = _brokerage_account_id(client)

    buy = client.post(
        "/api/investments/trades",
        headers=CSRF_HEADER,
        json={
            "account_id": brokerage_id,
            "ticker": "AAPL",
            "side": "buy",
            "quantity_q4": 1_0000,
            "price_q4": 100_000,
            "fee_cents": 0,
            "trade_date": "2026-11-09",
        },
    )
    assert buy.status_code == 200, buy.text

    sell = client.post(
        "/api/investments/trades",
        headers=CSRF_HEADER,
        json={
            "account_id": brokerage_id,
            "ticker": "AAPL",
            "side": "sell",
            "quantity_q4": 2_0000,
            "price_q4": 100_000,
            "fee_cents": 0,
            "trade_date": "2026-11-10",
        },
    )
    assert sell.status_code == 422, sell.text
