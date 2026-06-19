from __future__ import annotations

import pandas as pd

from quant_llm.paper_trading import build_latest_signals, run_paper_account_update
from quant_llm.market_rules import CHINA_A_RULES


class DummyModel:
    def predict_proba(self, features):
        return [[0.40, 0.60], [0.70, 0.30]]


def test_build_latest_signals_uses_latest_date_and_threshold() -> None:
    features = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-02"]),
            "symbol": ["AAPL.US", "AAPL.US", "MSFT.US"],
            "close": [100.0, 110.0, 220.0],
            "ret_1d": [0.01, 0.02, -0.01],
        }
    )

    signals = build_latest_signals(features, DummyModel(), ["ret_1d"], threshold=0.55)

    assert signals["date"].nunique() == 1
    assert signals["date"].iloc[0] == pd.Timestamp("2024-01-02")
    assert signals.loc[signals["symbol"] == "AAPL.US", "action"].iloc[0] == "long"
    assert signals.loc[signals["symbol"] == "MSFT.US", "action"].iloc[0] == "flat"


def test_run_paper_account_update_writes_orders_and_portfolio(tmp_path) -> None:
    signals = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-02"]),
            "symbol": ["AAPL.US", "MSFT.US"],
            "close": [100.0, 200.0],
            "prob_up": [0.60, 0.40],
            "target_position": [1.0, 0.0],
            "action": ["long", "flat"],
        }
    )

    summary = run_paper_account_update(
        signals,
        output_dir=tmp_path,
        starting_cash=10_000.0,
        max_symbol_weight=0.25,
        transaction_cost_bps=0.0,
    )

    assert summary["long_count"] == 1
    assert (tmp_path / "paper_orders.csv").exists()
    assert (tmp_path / "paper_portfolio.csv").exists()
    assert (tmp_path / "paper_summary.json").exists()

    portfolio = pd.read_csv(tmp_path / "paper_portfolio.csv")
    aapl = portfolio.loc[portfolio["symbol"] == "AAPL.US"].iloc[0]
    assert aapl["market_value"] == 2500.0


def test_run_paper_account_update_applies_china_a_lot_size(tmp_path) -> None:
    signals = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02"]),
            "symbol": ["600000.SH"],
            "close": [11.0],
            "prob_up": [0.60],
            "target_position": [1.0],
            "action": ["long"],
        }
    )

    run_paper_account_update(
        signals,
        output_dir=tmp_path,
        starting_cash=10_000.0,
        max_symbol_weight=0.25,
        transaction_cost_bps=0.0,
        market_rules=CHINA_A_RULES,
    )

    portfolio = pd.read_csv(tmp_path / "paper_portfolio.csv")
    assert portfolio.loc[0, "shares"] == 200.0
