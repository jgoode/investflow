from app.positions import average_cost_after_trade, realized_gain_loss_cents


def test_average_cost_and_realized_gain_are_integer_safe() -> None:
    avg_cost = average_cost_after_trade(
        prior_quantity_q4=10_0000,
        prior_avg_cost_q4=1_500_000,
        quantity_q4=2_5000,
        price_q4=1_600_000,
        fee_cents=250,
    )
    assert avg_cost == 1_522_000

    realized = realized_gain_loss_cents(
        sold_quantity_q4=1_0000,
        avg_cost_q4=1_522_000,
        sell_price_q4=1_700_000,
    )
    assert realized == 1_780
