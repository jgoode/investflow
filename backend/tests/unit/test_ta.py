from __future__ import annotations

from app.ta import compute_indicator_snapshot


def test_indicator_snapshot_matches_reference_fixture() -> None:
    closes = [
        100.0,
        101.0,
        102.0,
        101.8,
        103.2,
        105.1,
        104.5,
        106.0,
        107.7,
        108.4,
        110.2,
        109.8,
        111.5,
        112.0,
        111.3,
        113.2,
        114.6,
        113.9,
        115.3,
        116.7,
        117.1,
        116.8,
        118.5,
        119.2,
        120.1,
    ]
    snapshot = compute_indicator_snapshot(closes)

    assert snapshot["status"] == "ready"
    assert abs(snapshot["sma_3"][-1] - 119.26666666666667) < 1e-6
    assert abs(snapshot["ema_3"][-1] - 119.23403288125992) < 1e-6
    assert abs(snapshot["rsi_3"][-1] - 94.81988788205487) < 1e-6


def test_indicator_snapshot_handles_insufficient_history() -> None:
    snapshot = compute_indicator_snapshot([100.0, 101.0, 102.0])
    assert snapshot["status"] == "insufficient_data"
    assert snapshot["message"] == "insufficient data"
