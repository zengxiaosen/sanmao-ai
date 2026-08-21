from __future__ import annotations

import numpy as np
import pandas as pd

from quant_llm.regime import REGIME_LABELS, detect_regimes, factor_regime_performance


def _fake_price_features(n: int = 200) -> pd.DataFrame:
    """构造一段先涨后跌的价格特征（不联网）。"""
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    up = np.linspace(100, 180, n // 2)
    down = np.linspace(180, 120, n - n // 2)
    close = np.concatenate([up, down])
    frame = pd.DataFrame({"date": dates, "symbol": "NVDA.US", "close": close})
    frame["ret_1d"] = frame["close"].pct_change()
    frame["vol_20d"] = frame["ret_1d"].rolling(20).std()
    return frame


def _fake_macro(n: int = 200, vix: float = 15.0) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame({"date": dates, "vix_level": vix, "vix_change_5d": 0.0})


def test_detect_regimes_labels_bull_and_bear() -> None:
    regimes = detect_regimes(_fake_price_features(), _fake_macro(vix=15.0))
    assert set(regimes["regime"]).issubset(set(REGIME_LABELS))
    # 前半段持续上涨应出现 bull，后半段持续下跌应出现 bear。
    assert (regimes["regime"] == "bull 上行").any()
    assert (regimes["regime"] == "bear 下行").any()


def test_detect_regimes_high_vix_wins() -> None:
    # VIX 高于阈值时，无论涨跌都应标成高波动。
    regimes = detect_regimes(_fake_price_features(), _fake_macro(vix=40.0))
    assert (regimes["regime"] == "high_vol 高波动").all()


def test_detect_regimes_without_macro_falls_back_to_own_vol() -> None:
    regimes = detect_regimes(_fake_price_features(), None)
    assert len(regimes) > 0
    assert set(regimes["regime"]).issubset(set(REGIME_LABELS))


def test_factor_regime_performance_groups() -> None:
    regimes = detect_regimes(_fake_price_features(), _fake_macro(vix=15.0))
    dates = regimes["date"].dt.strftime("%Y-%m-%d").tolist()[:60]
    betas = pd.DataFrame(
        {
            "date": dates * 2,
            "factor": ["ret_5d"] * 60 + ["vix_level"] * 60,
            "beta": [0.001] * 60 + [-0.002] * 60,
            "tstat": [2.0] * 60 + [-1.0] * 60,
        }
    )
    perf = factor_regime_performance(betas, regimes)
    assert not perf.empty
    assert set(perf.columns) == {"regime", "factor", "mean_beta", "mean_abs_t", "days"}
    # |t| 取的是绝对值平均
    vix_rows = perf[perf["factor"] == "vix_level"]
    assert (vix_rows["mean_abs_t"] == 1.0).all()


def test_factor_regime_performance_empty_inputs() -> None:
    empty = factor_regime_performance(pd.DataFrame(), pd.DataFrame())
    assert empty.empty
