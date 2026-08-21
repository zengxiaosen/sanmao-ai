from __future__ import annotations

import pandas as pd

from quant_llm.review import build_review, render_review_markdown


def _decay_table() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"factor": "ret_5d", "status": "active", "recent_importance": 0.2, "importance_trend": 0.01, "recent_abs_t": 2.0},
            {"factor": "ma_gap_50d", "status": "failed", "recent_importance": 0.02, "importance_trend": -0.05, "recent_abs_t": 0.3},
        ]
    )


def _replacements() -> pd.DataFrame:
    return pd.DataFrame(
        [{"failed_factor": "ma_gap_50d", "group": "price_volume", "replacement": "ret_5d", "replacement_importance": 0.2}]
    )


def _regimes() -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=30, freq="B")
    return pd.DataFrame({"date": dates, "regime": ["bull 上行"] * 20 + ["high_vol 高波动"] * 10})


def _importance() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"window_end": "2026-05-01", "factor": "ret_5d", "importance": 0.5},
            {"window_end": "2026-05-01", "factor": "vix_level", "importance": 0.3},
        ]
    )


def test_build_review_full_inputs() -> None:
    review = build_review(
        backtest_summary={"annual_return": 0.25, "sharpe": 1.1, "max_drawdown": -0.2},
        decay_table=_decay_table(),
        replacements=_replacements(),
        regimes=_regimes(),
        latest_signal={"date": "2026-08-18", "action": "long 持有", "prob_up": 0.61},
        importance_timeline=_importance(),
        data_range=("2018-01-01", "2026-08-18"),
    )
    assert review["regime"]["latest"] == "high_vol 高波动"
    assert review["factor_health"]["failed"] == 1
    assert review["top_factors"][0]["factor"] == "ret_5d"
    assert review["replacements"][0]["replacement"] == "ret_5d"
    # 每个板块都应产出至少一句人话
    assert len(review["narrative"]) >= 5

    markdown = render_review_markdown(review)
    assert "策略复盘报告" in markdown
    assert "结论速读" in markdown


def test_build_review_tolerates_missing_inputs() -> None:
    review = build_review(
        backtest_summary={},
        decay_table=None,
        replacements=None,
        regimes=None,
        latest_signal=None,
        importance_timeline=None,
    )
    assert isinstance(review["narrative"], list)
    markdown = render_review_markdown(review)
    assert "策略复盘报告" in markdown
