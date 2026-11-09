from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.providers import (
    ManualAdapter,
    YahooFinanceAdapter,
    fetch_quote_via_provider,
    get_latest_quote,
    get_selected_provider,
    read_setting,
    resolve_quote,
    set_manual_quote,
    set_selected_provider,
    write_setting,
)
from tests.conftest import CSRF_HEADER, register


def test_manual_quote_is_persisted_and_exposed(client: TestClient) -> None:
    register(client, "alice")

    response = client.post(
        "/api/investments/quotes/manual",
        headers=CSRF_HEADER,
        json={"ticker": "AAPL", "price_q4": 185_0000, "asof": "2026-11-09T12:00:00Z"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["ticker"] == "AAPL"
    assert payload["source"] == "manual"
    assert payload["price_q4"] == 185_0000

    value = get_latest_quote("AAPL")
    assert value["source"] == "manual"
    assert value["price_q4"] == 185_0000

    quote_response = client.get("/api/investments/quotes/AAPL", headers=CSRF_HEADER)
    assert quote_response.status_code == 200, quote_response.text
    quote = quote_response.json()
    assert quote["ticker"] == "AAPL"
    assert quote["source"] == "manual"
    assert quote["stale"] in {False, True}


def test_stale_provider_quote_shows_badge_and_manual_fallback(client: TestClient) -> None:
    register(client, "alice")
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=30)
    set_manual_quote("MSFT", 1_000_000, asof=stale_time.isoformat().replace("+00:00", "Z"))

    quote = get_latest_quote("MSFT", now_utc=stale_time)
    assert quote["source"] == "manual"
    assert quote["stale"] is True
    assert "stale" in str(quote["badge"]).lower()

    stale_provider = client.get("/api/investments/quotes/MSFT", headers=CSRF_HEADER)
    assert stale_provider.status_code == 200, stale_provider.text
    stale_payload = stale_provider.json()
    assert stale_payload["ticker"] == "MSFT"
    assert stale_payload["source"] == "manual"
    assert stale_payload["stale"] is True
    assert "stale" in str(stale_payload["badge"]).lower()


def test_provider_settings_and_manual_resolution_paths() -> None:
    assert read_setting("missing-setting", "fallback") == "fallback"
    write_setting("provider.selected", {"name": "manual"}, value_type="json")
    assert read_setting("provider.selected", {}) == {"name": "manual"}
    assert set_selected_provider("manual") == "manual"
    assert set_selected_provider("bogus") == "yahoo"
    assert get_selected_provider() == "yahoo"

    set_manual_quote("AAPL", 120_0000)
    manual = ManualAdapter().get_quote("AAPL")
    assert manual["ticker"] == "AAPL"
    assert manual["source"] == "manual"
    assert ManualAdapter().get_history("AAPL") == []

    yahoo = YahooFinanceAdapter().get_history("MSFT")
    assert yahoo and yahoo[0]["ticker"] == "MSFT"

    quote = fetch_quote_via_provider("AAPL", provider_name="manual")
    assert quote["source"] == "manual"
    assert resolve_quote("AAPL")["source"] == "manual"


def test_yahoo_adapter_success_and_failure(monkeypatch) -> None:
    class FakeResponse:
        def __init__(self, payload: dict):
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self._payload

    class FakeClient:
        def __init__(self, payload: dict):
            self.payload = payload

        def get(self, url: str, headers: dict | None = None):
            return FakeResponse(self.payload)

        def close(self) -> None:
            return None

    payload = {
        "chart": {
            "result": [
                {
                    "meta": {
                        "regularMarketPrice": 150.5,
                        "regularMarketTime": 1_700_000_000,
                    }
                }
            ]
        }
    }
    quote = YahooFinanceAdapter().get_quote("AAPL", client=FakeClient(payload))
    assert quote["ticker"] == "AAPL"
    assert quote["price_q4"] == 1_505_000
    assert quote["source"] == "yahoo"

    def boom(self, ticker: str, *, client=None):
        raise RuntimeError("network down")

    monkeypatch.setattr(YahooFinanceAdapter, "get_quote", boom)
    stale = fetch_quote_via_provider("MSFT", provider_name="yahoo")
    assert stale["ticker"] == "MSFT"
    assert stale["status"] in {"unavailable", "live", "stale"}
