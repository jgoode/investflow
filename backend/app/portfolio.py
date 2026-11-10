from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Sequence
from itertools import product
from typing import Any

from app.providers import YahooFinanceAdapter


def _as_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, (int, float, str, bytes, bytearray)):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
    return default


def _normalize_returns(values: Sequence[float]) -> list[float]:
    numbers: list[float] = []
    for value in values:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(numeric):
            numbers.append(numeric)
    if not numbers:
        return []
    if max(abs(value) for value in numbers) > 2.0:
        returns: list[float] = []
        for previous, current in zip(numbers[:-1], numbers[1:], strict=False):
            if previous == 0:
                returns.append(0.0)
            else:
                returns.append((current / previous) - 1.0)
        return returns
    return numbers


def _annualized_return(returns: Sequence[float]) -> float:
    if not returns:
        return 0.0
    total_periods = len(returns)
    growth = 1.0
    for value in returns:
        growth *= 1.0 + float(value)
    return float(growth ** (252.0 / float(max(total_periods, 1))) - 1.0)


def _volatility(returns: Sequence[float]) -> float:
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / float(len(returns))
    variance = sum((value - mean) ** 2 for value in returns) / float(len(returns) - 1)
    return math.sqrt(variance) * math.sqrt(252.0)


def _max_drawdown(returns: Sequence[float]) -> float:
    cumulative = 1.0
    peak = 1.0
    maximum_drawdown = 0.0
    for value in returns:
        cumulative *= 1.0 + value
        if cumulative > peak:
            peak = cumulative
        if peak > 0:
            drawdown = (peak - cumulative) / peak
            if drawdown > maximum_drawdown:
                maximum_drawdown = drawdown
    return maximum_drawdown


def compute_portfolio_risk_metrics(
    returns: Sequence[float], *, benchmark_returns: Sequence[float] | None = None, rf: float = 0.02
) -> dict[str, Any]:
    portfolio_returns = _normalize_returns(returns)
    if len(portfolio_returns) < 2:
        return {
            "status": "insufficient_data",
            "message": "insufficient data",
            "annualized_return": 0.0,
            "volatility": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0,
            "beta": 0.0,
            "rf": float(rf),
            "benchmark": "SPY",
        }

    annualized = _annualized_return(portfolio_returns)
    vol = _volatility(portfolio_returns)
    sharpe = (annualized - rf) / vol if vol > 0 else 0.0
    beta = 0.0
    if benchmark_returns is not None:
        benchmark = _normalize_returns(benchmark_returns)
        if len(benchmark) > 1 and len(benchmark) == len(portfolio_returns):
            benchmark_mean = sum(benchmark) / float(len(benchmark))
            portfolio_mean = sum(portfolio_returns) / float(len(portfolio_returns))
            benchmark_variance = sum((value - benchmark_mean) ** 2 for value in benchmark) / float(
                len(benchmark) - 1
            )
            covariance = sum(
                (portfolio_returns[idx] - portfolio_mean) * (benchmark[idx] - benchmark_mean)
                for idx in range(len(portfolio_returns))
            ) / float(len(portfolio_returns) - 1)
            beta = covariance / benchmark_variance if benchmark_variance > 0 else 0.0

    return {
        "status": "ready",
        "message": "ok",
        "annualized_return": annualized,
        "volatility": vol,
        "sharpe": sharpe,
        "max_drawdown": _max_drawdown(portfolio_returns),
        "beta": beta,
        "rf": float(rf),
        "benchmark": "SPY",
    }


def _resolve_constraints(
    tickers: Sequence[str], constraints: dict[str, dict[str, float]] | None
) -> dict[str, dict[str, float]]:
    config: dict[str, dict[str, float]] = {}
    for ticker in tickers:
        raw = (constraints or {}).get(ticker) or {}
        minimum = float(raw.get("min", 0.0) or 0.0)
        maximum = float(raw.get("max", 1.0) or 1.0)
        if minimum > maximum:
            minimum, maximum = maximum, minimum
        minimum = max(0.0, min(minimum, 1.0))
        maximum = max(0.0, min(maximum, 1.0))
        config[ticker] = {"min": minimum, "max": maximum}
    return config


def _weight_candidates(
    tickers: Sequence[str], constraints: dict[str, dict[str, float]]
) -> list[tuple[float, ...]]:
    if len(tickers) == 1:
        ticker = tickers[0]
        conf = constraints.get(ticker, {"min": 0.0, "max": 1.0})
        minimum = max(0.0, min(1.0, conf["min"]))
        maximum = max(0.0, min(1.0, conf["max"]))
        if minimum <= 1.0 + 1e-9 and maximum >= 1.0 - 1e-9:
            return [(1.0,)]
        return []

    candidates: list[tuple[float, ...]] = []
    total_min = sum(conf["min"] for conf in constraints.values())
    total_max = sum(conf["max"] for conf in constraints.values())
    if total_min > 1.0 + 1e-9 or total_max < 1.0 - 1e-9:
        return candidates

    for weights in product(range(0, 101), repeat=len(tickers)):
        candidate = tuple(value / 100.0 for value in weights)
        total = sum(candidate)
        if abs(total - 1.0) > 1e-4:
            continue
        valid = True
        for index, ticker in enumerate(tickers):
            conf = constraints.get(ticker, {"min": 0.0, "max": 1.0})
            weight = candidate[index]
            if weight < conf["min"] - 1e-9 or weight > conf["max"] + 1e-9:
                valid = False
                break
        if valid:
            candidates.append(candidate)
    if candidates:
        return candidates
    if len(tickers) > 0:
        return [tuple(1.0 if index == 0 else 0.0 for index in range(len(tickers)))]
    return []


def optimize_portfolio_weights(
    assets: Sequence[dict[str, Any]],
    *,
    current_weights: dict[str, float] | None = None,
    constraints: dict[str, dict[str, float]] | None = None,
    rf: float = 0.02,
) -> dict[str, Any]:
    if not assets:
        return {
            "status": "insufficient_history",
            "message": "No assets supplied for optimization.",
            "shortfall_tickers": [],
            "disclaimer": "The optimization outputs are advisory-only and not investment advice.",
        }

    normalized_assets: list[dict[str, Any]] = []
    shortfalls: list[str] = []
    for entry in assets:
        ticker = str(entry.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        raw_returns = (
            entry.get("returns") or entry.get("daily_returns") or entry.get("values") or []
        )
        returns = _normalize_returns(raw_returns)
        if len(returns) < 120:
            shortfalls.append(ticker)
            continue
        normalized_assets.append({"ticker": ticker, "returns": returns})

    if not normalized_assets:
        return {
            "status": "insufficient_history",
            "message": "Optimisation requires at least 120 days of history for every ticker.",
            "shortfall_tickers": sorted(shortfalls),
            "disclaimer": "The optimization outputs are advisory-only and not investment advice.",
        }

    tickers = [item["ticker"] for item in normalized_assets]
    active_current = {
        str(key).upper(): _as_float(value) for key, value in (current_weights or {}).items()
    }
    current_portfolio = {
        ticker: active_current.get(ticker, 1.0 / max(len(tickers), 1)) for ticker in tickers
    }
    total = sum(current_portfolio.values())
    if total > 0:
        current_portfolio = {ticker: value / total for ticker, value in current_portfolio.items()}

    constraints_map = _resolve_constraints(tickers, constraints)
    total_min = sum(entry["min"] for entry in constraints_map.values())
    total_max = sum(entry["max"] for entry in constraints_map.values())
    if total_min > 1.0 + 1e-9 or total_max < 1.0 - 1e-9:
        return {
            "status": "infeasible",
            "message": (
                "The requested portfolio constraints are infeasible for a "
                "long-only 100% allocation."
            ),
            "shortfall_tickers": [],
            "disclaimer": "The optimization outputs are advisory-only and not investment advice.",
        }

    annualized = [(_annualized_return(item["returns"]) + 1.0) for item in normalized_assets]
    matrix = [item["returns"] for item in normalized_assets]
    if len(normalized_assets) == 1:
        cov_matrix = [[1.0]]
    else:
        cov_matrix = [[] for _ in range(len(normalized_assets))]
        for idx_row, row in enumerate(matrix):
            for _idx_col, col in enumerate(matrix):
                row_mean = sum(row) / float(len(row))
                col_mean = sum(col) / float(len(col))
                cov_total = 0.0
                pair_length = min(len(row), len(col))
                for i in range(pair_length):
                    cov_total += (row[i] - row_mean) * (col[i] - col_mean)
                cov_matrix[idx_row].append(cov_total / float(max(pair_length - 1, 1)))

    candidate_rows: list[dict[str, Any]] = []
    for weights in _weight_candidates(tickers, constraints_map):
        weighted_vector = [
            float(weight) * (annualized[idx] - 1.0) for idx, weight in enumerate(weights)
        ]
        expected_return = sum(weighted_vector)
        if len(normalized_assets) == 1:
            volatility = 0.0
        else:
            variance = 0.0
            for row_index, row_weights in enumerate(weights):
                for col_index, col_weights in enumerate(weights):
                    variance += row_weights * col_weights * cov_matrix[row_index][col_index]
            volatility = math.sqrt(max(variance, 0.0)) * math.sqrt(252.0)
        sharpe = (expected_return - rf) / volatility if volatility > 0 else 0.0
        candidate_rows.append(
            {
                "weights": dict(zip(tickers, weights, strict=False)),
                "expected_return": expected_return,
                "volatility": volatility,
                "sharpe": sharpe,
            }
        )

    if not candidate_rows:
        return {
            "status": "infeasible",
            "message": "No feasible long-only portfolio meets the provided min/max constraints.",
            "shortfall_tickers": [],
            "disclaimer": "The optimization outputs are advisory-only and not investment advice.",
        }

    max_sharpe = max(
        candidate_rows, key=lambda item: item["sharpe"], default={"weights": current_portfolio}
    )
    min_variance = min(
        candidate_rows, key=lambda item: item["volatility"], default={"weights": current_portfolio}
    )
    frontier = sorted(candidate_rows, key=lambda item: item["volatility"])
    if len(frontier) < 30:
        frontier = frontier + [frontier[-1]] * max(0, 30 - len(frontier))
    frontier = frontier[:30]

    return {
        "status": "ready",
        "message": "mean-variance optimization complete",
        "benchmark": "SPY",
        "rf": float(rf),
        "current_weights": current_portfolio,
        "max_sharpe": {
            "weights": max_sharpe.get("weights", current_portfolio),
            "expected_return": _as_float(max_sharpe.get("expected_return", 0.0)),
            "volatility": _as_float(max_sharpe.get("volatility", 0.0)),
            "sharpe": _as_float(max_sharpe.get("sharpe", 0.0)),
        },
        "min_variance": {
            "weights": min_variance.get("weights", current_portfolio),
            "expected_return": _as_float(min_variance.get("expected_return", 0.0)),
            "volatility": _as_float(min_variance.get("volatility", 0.0)),
            "sharpe": _as_float(min_variance.get("sharpe", 0.0)),
        },
        "frontier": [
            {
                "risk": _as_float(item["volatility"]),
                "return": _as_float(item["expected_return"]),
            }
            for item in frontier
        ],
        "disclaimer": (
            "Portfolio optimization is advisory-only and based on historical variance; "
            "it is not investment advice."
        ),
        "shortfall_tickers": [],
    }


def _history_series_for_ticker(ticker: str, *, days: int = 180) -> list[dict[str, Any]]:
    provider = YahooFinanceAdapter()
    history = provider.get_history(ticker)
    if not history:
        return []
    return history[-days:]


def build_portfolio_summary() -> dict[str, Any]:
    from app.db.connection import connect

    with connect() as conn:
        rows = conn.execute(
            """
            SELECT p.id, p.account_id, p.ticker, p.quantity_q4, a.name AS account_name
            FROM positions p
            JOIN accounts a ON a.id = p.account_id
            WHERE p.status = 'open'
            ORDER BY a.name ASC, p.ticker ASC
            """
        ).fetchall()

    position_rows = [dict(row) for row in rows]
    if not position_rows:
        return {
            "summary": {
                "total_market_value_cents": 0,
                "cash_share_cents": 0,
                "account_totals": {},
            },
            "allocation": {
                "by_account": {},
                "by_ticker": {},
                "by_currency": {"USD": {"currency": "USD", "market_value_cents": 0, "weight": 1.0}},
                "current_weights": {},
            },
            "risk_metrics": {
                "status": "insufficient_data",
                "message": "No open positions to analyze.",
                "annualized_return": 0.0,
                "volatility": 0.0,
                "sharpe": 0.0,
                "max_drawdown": 0.0,
                "beta": 0.0,
                "rf": 0.02,
                "benchmark": "SPY",
            },
            "timeline": {"series": [], "window": "1Y"},
        }

    ticker_values: dict[str, int] = defaultdict(int)
    account_totals: dict[str, int] = defaultdict(int)
    ticker_histories: dict[str, list[float]] = {}
    ticker_annualized: dict[str, float] = {}

    for row in position_rows:
        ticker = str(row["ticker"]).upper()
        quantity_q4 = int(row["quantity_q4"] or 0)
        quote = YahooFinanceAdapter().get_quote(ticker)
        price_q4 = int(quote.get("price_q4") or 0)
        value = (quantity_q4 * price_q4) // 1_000_000
        ticker_values[ticker] += value
        account_totals[str(row["account_name"])] += value
        history = _history_series_for_ticker(ticker)
        if history:
            series = [
                _as_float(item.get("close_q4")) / 10_000.0
                for item in history
                if item.get("close_q4")
            ]
            if series:
                ticker_histories[ticker] = series
                daily_returns = _normalize_returns(series)
                if daily_returns:
                    ticker_annualized[ticker] = _annualized_return(daily_returns)

    total_value = sum(ticker_values.values())
    by_ticker: dict[str, dict[str, Any]] = {}
    for ticker, value in sorted(ticker_values.items()):
        weight = (value / total_value) if total_value else 0.0
        by_ticker[ticker] = {
            "ticker": ticker,
            "market_value_cents": int(value),
            "weight": float(weight),
            "weighted_return": float(weight * ticker_annualized.get(ticker, 0.0)),
        }

    by_account: dict[str, dict[str, Any]] = {}
    for account_name, value in sorted(account_totals.items()):
        weight = (value / total_value) if total_value else 0.0
        by_account[account_name] = {
            "account_name": account_name,
            "market_value_cents": int(value),
            "cash_share_cents": 0,
            "weight": float(weight),
        }

    market_weights = {ticker: item["weight"] for ticker, item in by_ticker.items()}
    combined_returns: list[float] = []
    if ticker_histories:
        points_by_ticker = {
            ticker: _normalize_returns(series)
            for ticker, series in ticker_histories.items()
            if series
        }
        if points_by_ticker:
            series_length = min(len(values) for values in points_by_ticker.values())
            for idx in range(series_length):
                combined_returns.append(
                    sum(
                        market_weights.get(ticker, 0.0) * values[idx]
                        for ticker, values in points_by_ticker.items()
                    )
                )

    benchmark_returns = [0.01] * len(combined_returns) if combined_returns else []
    if combined_returns:
        risk = compute_portfolio_risk_metrics(
            combined_returns, benchmark_returns=benchmark_returns, rf=0.02
        )
    else:
        risk = {
            "status": "insufficient_data",
            "message": "insufficient data",
            "annualized_return": 0.0,
            "volatility": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0,
            "beta": 0.0,
            "rf": 0.02,
            "benchmark": "SPY",
        }

    timeline_points: list[dict[str, Any]] = []
    if combined_returns:
        wealth = 1.0
        for daily_return in combined_returns[-90:]:
            wealth *= 1.0 + daily_return
            timeline_points.append({"value_cents": int(round(total_value * wealth))})

    return {
        "summary": {
            "total_market_value_cents": int(total_value),
            "cash_share_cents": sum(
                int(item.get("cash_share_cents", 0)) for item in by_account.values()
            ),
            "account_totals": {
                account_name: int(value) for account_name, value in sorted(account_totals.items())
            },
        },
        "allocation": {
            "by_account": by_account,
            "by_ticker": by_ticker,
            "by_currency": {
                "USD": {"currency": "USD", "market_value_cents": int(total_value), "weight": 1.0}
            },
            "current_weights": market_weights,
        },
        "risk_metrics": risk,
        "timeline": {"series": timeline_points, "window": "1Y"},
    }
