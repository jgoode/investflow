from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import CSRF_HEADER, register


def test_dashboard_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/dashboard")
    assert response.status_code == 401


def test_dashboard_returns_cards_and_empty_state(client: TestClient) -> None:
    register(client, "alice")

    response = client.get("/api/dashboard", headers=CSRF_HEADER)
    assert response.status_code == 200, response.text

    payload = response.json()["dashboard"]
    assert payload["empty"] is True
    assert "cards" in payload
    assert "net_worth" in payload["cards"]
    assert "cash_flow" in payload["cards"]
    assert "recent_transactions" in payload["cards"]
    assert payload["cards"]["recent_transactions"]["items"] == []
