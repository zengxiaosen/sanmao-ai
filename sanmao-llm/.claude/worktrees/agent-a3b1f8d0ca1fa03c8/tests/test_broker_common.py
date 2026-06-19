from __future__ import annotations

import pandas as pd

from quant_llm.brokers.common import (
    build_broker_order_plan,
    check_order_risk_limits,
    reconcile_paper_portfolio_with_alpaca,
)


def test_build_broker_order_plan_skips_holds_and_small_orders() -> None:
    paper_orders = pd.DataFrame(
        {
            "run_id": ["r1", "r1", "r1"],
            "symbol": ["AAPL.US", "MSFT.US", "SPY.US"],
            "action": ["buy", "sell", "hold"],
            "delta_shares": [1.5, -0.1, 0.0],
            "notional": [300.0, -5.0, 0.0],
        }
    )

    plan = build_broker_order_plan(paper_orders, min_notional=10.0)

    assert plan.loc[plan["symbol"] == "AAPL.US", "side"].iloc[0] == "buy"
    assert plan.loc[plan["symbol"] == "AAPL.US", "qty"].iloc[0] == 1.5
    assert plan.loc[plan["symbol"] == "MSFT.US", "side"].iloc[0] == "hold"
    assert plan.loc[plan["symbol"] == "SPY.US", "side"].iloc[0] == "hold"


def test_check_order_risk_limits_blocks_open_orders() -> None:
    order_plan = pd.DataFrame({"side": ["buy"], "notional": [1000.0]})
    passed, reasons = check_order_risk_limits(
        order_plan,
        account={"status": "ACTIVE", "portfolio_value": "100000"},
        open_orders=[{"id": "existing"}],
        risk_config={"block_if_open_orders": True},
    )

    assert passed is False
    assert any("open_orders" in reason and "FAIL" in reason for reason in reasons)


def test_check_order_risk_limits_blocks_too_large_order() -> None:
    order_plan = pd.DataFrame({"side": ["buy"], "notional": [40000.0]})
    passed, reasons = check_order_risk_limits(
        order_plan,
        account={"status": "ACTIVE", "portfolio_value": "100000"},
        open_orders=[],
        risk_config={"max_order_notional_pct": 0.30},
    )

    assert passed is False
    assert any("max_order_notional" in reason and "FAIL" in reason for reason in reasons)


def test_reconcile_paper_portfolio_with_alpaca_matches_positions() -> None:
    paper_portfolio = pd.DataFrame(
        {
            "run_id": ["r1", "r1"],
            "symbol": ["MSFT.US", "AAPL.US"],
            "shares": [10.0, 0.0],
        }
    )
    positions = [{"symbol": "MSFT", "qty": "10"}]

    reconciliation = reconcile_paper_portfolio_with_alpaca(paper_portfolio, positions)

    assert bool(reconciliation.loc[reconciliation["symbol"] == "MSFT", "matched"].iloc[0]) is True
