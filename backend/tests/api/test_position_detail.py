from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import CSRF_HEADER, register


def _find_account_by_name(tree: list[dict], name: str) -> dict | None:
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


def test_position_detail_contract_includes_summary_valuation_and_news(client: TestClient) -> None:
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
            "price_q4": 1_500_000,
            "fee_cents": 0,
            "trade_date": "2026-11-09",
        },
    )
    assert buy.status_code == 200, buy.text

    response = client.get("/api/investments/positions/AAPL/detail", headers=CSRF_HEADER)
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["ticker"] == "AAPL"
    assert payload["ticker_summary"]["ticker"] == "AAPL"
    assert payload["valuation_breakdown"]["market_value_cents"] >= 0
    assert payload["historical_context"]["price_points"]
    assert isinstance(payload["news"], list)
    assert "stale" in payload["ticker_summary"]


def test_position_detail_is_available_by_position_id(client: TestClient) -> None:
    register(client, "alice")
    brokerage_id = _brokerage_account_id(client)

    buy = client.post(
        "/api/investments/trades",
        headers=CSRF_HEADER,
        json={
            "account_id": brokerage_id,
            "ticker": "MSFT",
            "side": "buy",
            "quantity_q4": 1_0000,
            "price_q4": 250_000,
            "fee_cents": 0,
            "trade_date": "2026-11-09",
        },
    )
    assert buy.status_code == 200, buy.text
    position_id = buy.json()["position"]["id"]

    response = client.get(f"/api/investments/positions/{position_id}/detail", headers=CSRF_HEADER)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["ticker"] == "MSFT"
    assert payload["ticker_summary"]["position_id"] == position_id
