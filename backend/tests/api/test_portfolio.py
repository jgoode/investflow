from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.portfolio import (
    _as_float,
    _normalize_returns,
    _resolve_constraints,
    _weight_candidates,
    build_portfolio_summary,
    compute_portfolio_risk_metrics,
    optimize_portfolio_weights,
)
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


def test_portfolio_summary_and_metrics_contract(client: TestClient) -> None:
    register(client, "alice")
    brokerage_id = _brokerage_account_id(client)

    client.post(
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
    client.post(
        "/api/investments/trades",
        headers=CSRF_HEADER,
        json={
            "account_id": brokerage_id,
            "ticker": "MSFT",
            "side": "buy",
            "quantity_q4": 1_5000,
            "price_q4": 2_000_000,
            "fee_cents": 0,
            "trade_date": "2026-11-09",
        },
    )

    response = client.get("/api/investments/portfolio", headers=CSRF_HEADER)
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["summary"]["total_market_value_cents"] > 0
    assert payload["allocation"]["by_ticker"]["AAPL"]["weight"] > 0
    assert payload["allocation"]["by_ticker"]["MSFT"]["weight"] > 0
    assert "annualized_return" in payload["risk_metrics"]
    assert payload["risk_metrics"]["status"] in {"ready", "insufficient_data"}


def test_optimizer_handles_constraint_and_short_history() -> None:
    daily_returns = [0.012, -0.008, 0.015, 0.009, -0.006, 0.018, 0.011, -0.004]
    daily_returns = daily_returns * 15
    metrics = compute_portfolio_risk_metrics(daily_returns)
    assert metrics["annualized_return"] > 0
    assert metrics["volatility"] >= 0

    result = optimize_portfolio_weights(
        [
            {"ticker": "AAPL", "returns": daily_returns},
            {"ticker": "MSFT", "returns": daily_returns},
        ],
        current_weights={"AAPL": 0.6, "MSFT": 0.4},
        constraints={"AAPL": {"min": 0.2, "max": 0.7}, "MSFT": {"min": 0.3, "max": 0.8}},
    )
    assert result["status"] == "ready"
    assert result["max_sharpe"]["weights"]["AAPL"] >= 0.2
    assert result["min_variance"]["weights"]["MSFT"] >= 0.3
    assert result["disclaimer"]

    short = optimize_portfolio_weights(
        [{"ticker": "AAPL", "returns": [0.01, -0.02, 0.01]}],
        current_weights={"AAPL": 1.0},
    )
    assert short["status"] == "insufficient_history"
    assert short["shortfall_tickers"] == ["AAPL"]

    infeasible = optimize_portfolio_weights(
        [
            {"ticker": "AAPL", "returns": daily_returns},
            {"ticker": "MSFT", "returns": daily_returns},
        ],
        current_weights={"AAPL": 0.6, "MSFT": 0.4},
        constraints={"AAPL": {"min": 0.99, "max": 1.0}, "MSFT": {"min": 0.99, "max": 1.0}},
    )
    assert infeasible["status"] == "infeasible"
    assert "infeasible" in infeasible["message"].lower()


def test_portfolio_summary_contract_includes_weighted_returns_and_timeline() -> None:
    metrics = compute_portfolio_risk_metrics(
        [0.01, -0.02, 0.005, 0.015, -0.01, 0.012, 0.01, -0.018] * 15,
        benchmark_returns=[0.008, -0.015, 0.004, 0.013, -0.011, 0.010, 0.009, -0.014] * 15,
    )
    assert metrics["status"] == "ready"
    assert metrics["beta"] >= -1.0
    assert metrics["beta"] <= 2.0

    summary = {
        "summary": {
            "total_market_value_cents": 250_000,
            "cash_share_cents": 25_000,
            "account_totals": {"Brokerage A": 250_000},
        },
        "allocation": {
            "by_account": {
                "Brokerage A": {
                    "account_name": "Brokerage A",
                    "market_value_cents": 250_000,
                    "weight": 1.0,
                }
            },
            "by_ticker": {
                "AAPL": {
                    "ticker": "AAPL",
                    "market_value_cents": 150_000,
                    "weight": 0.6,
                    "weighted_return": 0.006,
                },
                "MSFT": {
                    "ticker": "MSFT",
                    "market_value_cents": 100_000,
                    "weight": 0.4,
                    "weighted_return": 0.004,
                },
            },
            "by_currency": {
                "USD": {"currency": "USD", "market_value_cents": 250_000, "weight": 1.0}
            },
            "current_weights": {"AAPL": 0.6, "MSFT": 0.4},
        },
        "timeline": {"series": [{"value_cents": 250_000}], "window": "1Y"},
    }
    assert "weighted_return" in summary["allocation"]["by_ticker"]["AAPL"]
    assert summary["timeline"]["window"] in {"1M", "3M", "6M", "1Y"}


def test_portfolio_helper_and_summary_edge_cases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Isolate from the dev DB (DEF-004): a migrated temp DB guarantees the empty
    # positions state asserted below — e2e runs leave real positions in the dev DB.
    db_path = tmp_path / "portfolio-test.db"
    monkeypatch.setenv("INVESTFLOW_DB_PATH", str(db_path))
    from tests.conftest import _alembic_upgrade_head

    _alembic_upgrade_head(db_path)
    assert _as_float("3.5") == 3.5
    assert _as_float({"bad": "value"}, 2.5) == 2.5
    assert _normalize_returns([1.0, "bad", float("nan"), 2.5]) == [1.5]
    assert _normalize_returns([1.0, 2.0, 4.0]) == [1.0, 1.0]
    assert _resolve_constraints(
        ["AAPL", "MSFT"],
        {"AAPL": {"min": 0.7, "max": 0.2}, "MSFT": {"min": 0.1, "max": 0.9}},
    ) == {
        "AAPL": {"min": 0.2, "max": 0.7},
        "MSFT": {"min": 0.1, "max": 0.9},
    }
    assert _weight_candidates(["AAPL"], {"AAPL": {"min": 0.0, "max": 0.5}}) == []
    candidates = _weight_candidates(
        ["AAPL", "MSFT"],
        {"AAPL": {"min": 0.9, "max": 1.0}, "MSFT": {"min": 0.0, "max": 0.1}},
    )
    assert (0.9, 0.1) in candidates

    empty = build_portfolio_summary()
    assert empty["summary"]["total_market_value_cents"] == 0
    assert empty["risk_metrics"]["status"] == "insufficient_data"

    one_asset = optimize_portfolio_weights(
        [{"ticker": "AAPL", "returns": [0.01] * 130}],
        current_weights={"AAPL": 0.5},
        constraints={"AAPL": {"min": 0.5, "max": 1.0}},
    )
    assert one_asset["status"] == "ready"
    assert one_asset["current_weights"]["AAPL"] == 1.0
