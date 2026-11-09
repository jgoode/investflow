from __future__ import annotations

import math
from collections.abc import Sequence


def _moving_average(values: Sequence[float], period: int) -> list[float]:
    if period <= 0 or len(values) < period:
        return []
    window: list[float] = []
    output: list[float] = []
    for value in values:
        window.append(float(value))
        if len(window) > period:
            window.pop(0)
        if len(window) == period:
            output.append(sum(window) / float(period))
    return output


def _ema(values: Sequence[float], period: int) -> list[float]:
    if period <= 0 or len(values) == 0:
        return []
    alpha = 2.0 / (period + 1.0)
    output: list[float] = []
    current = float(values[0])
    for value in values:
        current = (float(value) - current) * alpha + current
        output.append(current)
    return output


def _rsi(values: Sequence[float], period: int) -> list[float]:
    if len(values) <= period:
        return []
    deltas = [float(values[i]) - float(values[i - 1]) for i in range(1, len(values))]
    gains: list[float] = []
    losses: list[float] = []
    for delta in deltas:
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    avg_gain = sum(gains[:period]) / float(period)
    avg_loss = sum(losses[:period]) / float(period)
    output = [50.0]
    for idx in range(period, len(gains)):
        avg_gain = ((avg_gain * (period - 1)) + gains[idx]) / float(period)
        avg_loss = ((avg_loss * (period - 1)) + losses[idx]) / float(period)
        if avg_loss == 0:
            output.append(100.0)
        else:
            rs = avg_gain / avg_loss
            output.append(100.0 - (100.0 / (1.0 + rs)))
    return output


def _stddev(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    mean = sum(values) / float(len(values))
    variance = sum((item - mean) ** 2 for item in values) / float(len(values))
    return math.sqrt(variance)


def compute_indicator_snapshot(
    closes: Sequence[float], *, periods: Sequence[int] | None = None
) -> dict[str, object]:
    values = [float(item) for item in closes]
    if not values:
        return {
            "status": "insufficient_data",
            "message": "insufficient data",
            "periods": [],
            "points": 0,
        }
    configured = list(periods) if periods is not None else [3, 12, 20, 26, 50, 200]
    minimum = 20 if periods is None else max(configured)
    if len(values) < minimum:
        return {
            "status": "insufficient_data",
            "message": "insufficient data",
            "lookback": minimum,
            "points": len(values),
            "periods": [str(period) for period in configured],
        }

    snapshot: dict[str, object] = {
        "status": "ready",
        "message": "ok",
        "points": len(values),
        "lookback": minimum,
    }
    for period in configured:
        sma = _moving_average(values, period)
        if sma:
            snapshot[f"sma_{period}"] = sma
        ema = _ema(values, period)
        if ema:
            snapshot[f"ema_{period}"] = ema
        if period == 14:
            rsi = _rsi(values, 14)
            if rsi:
                snapshot["rsi_14"] = rsi
    if len(values) > 26:
        ema_12 = _ema(values, 12)
        ema_26 = _ema(values, 26)
        macd = [a - b for a, b in zip(ema_12, ema_26, strict=False)]
        signal = _ema(macd, 9)
        hist = [a - b for a, b in zip(macd[: len(signal)], signal, strict=False)]
        snapshot["macd_12_26_9"] = macd
        snapshot["macd_signal_9"] = signal
        snapshot["macd_histogram"] = hist
    if len(values) >= 20:
        window = values[-20:]
        mean = sum(window) / float(len(window))
        std = _stddev(window)
        upper = [mean + (2.0 * std)] * len(values)
        lower = [mean - (2.0 * std)] * len(values)
        snapshot["bollinger_upper_20_2"] = upper
        snapshot["bollinger_lower_20_2"] = lower
        snapshot["bollinger_mid_20_2"] = [mean] * len(values)
    snapshot["sma_3"] = _moving_average(values, 3)
    snapshot["ema_3"] = _ema(values, 3)
    snapshot["rsi_3"] = _rsi(values, 3) if len(values) > 3 else []
    return snapshot
