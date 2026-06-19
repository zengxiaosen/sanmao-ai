from __future__ import annotations

import pandas as pd

from quant_llm.features import FEATURE_COLUMNS, build_price_features


def test_build_price_features_has_target_and_features() -> None:
    dates = pd.date_range("2024-01-01", periods=80, freq="D")
    prices = pd.DataFrame(
        {
            "date": dates,
            "open": range(100, 180),
            "high": range(101, 181),
            "low": range(99, 179),
            "close": range(100, 180),
            "volume": [1000 + i for i in range(80)],
            "symbol": "TEST.US",
        }
    )
    features = build_price_features(prices)

    assert not features.empty
    assert set(FEATURE_COLUMNS).issubset(features.columns)
    assert {"future_ret", "target_up"}.issubset(features.columns)
    assert features["target_up"].isin([0, 1]).all()

