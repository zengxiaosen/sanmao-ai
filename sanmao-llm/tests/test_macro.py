from __future__ import annotations

import pandas as pd

from quant_llm.macro import (
    MACRO_FEATURE_COLUMNS,
    build_macro_features,
    join_macro_features,
)


def _fake_panel(n: int = 40) -> pd.DataFrame:
    """造一个假的宏观面板（不联网），列：date + vix + ust10y + dxy。"""
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame(
        {
            "date": dates,
            "vix": [15 + (i % 7) for i in range(n)],
            "ust10y": [40 + 0.1 * i for i in range(n)],
            "dxy": [100 + 0.05 * i for i in range(n)],
        }
    )


def test_build_macro_features_produces_expected_columns() -> None:
    panel = _fake_panel()
    macro = build_macro_features(panel)
    assert not macro.empty
    # 至少包含 level + change 系列的列
    for col in ["vix_level", "vix_change_5d", "ust10y_level", "ust10y_change_5d", "dxy_change_5d"]:
        assert col in macro.columns


def test_join_macro_features_fills_missing_with_zero() -> None:
    # 价格特征：两只股票、同样的日期。
    dates = pd.date_range("2024-01-01", periods=40, freq="D")
    price = pd.DataFrame(
        {
            "date": list(dates) * 2,
            "symbol": ["NVDA.US"] * 40 + ["AAPL.US"] * 40,
            "close": range(80),
        }
    )
    macro = build_macro_features(_fake_panel())
    merged = join_macro_features(price, macro)

    # 所有价格行都保留（left join），宏观列都存在且无 NaN。
    assert len(merged) == len(price)
    for col in MACRO_FEATURE_COLUMNS:
        assert col in merged.columns
        assert merged[col].notna().all()


def test_join_macro_features_handles_empty_macro() -> None:
    # 宏观全拉失败的极端情况：merge 后宏观列应全部填 0，主链路不挂。
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    price = pd.DataFrame({"date": dates, "symbol": "NVDA.US", "close": range(10)})
    empty_macro = pd.DataFrame(columns=["date", *MACRO_FEATURE_COLUMNS])
    merged = join_macro_features(price, empty_macro)
    assert len(merged) == len(price)
    for col in MACRO_FEATURE_COLUMNS:
        assert (merged[col] == 0.0).all()
