from __future__ import annotations

import numpy as np
import pandas as pd


FEATURE_COLUMNS = [
    "ret_1d",
    "ret_5d",
    "ret_20d",
    "vol_20d",
    "ma_gap_10d",
    "ma_gap_50d",
    "range_1d",
    "volume_z_20d",
]


def build_price_features(prices: pd.DataFrame, horizon_days: int = 1) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for symbol, group in prices.groupby("symbol", sort=False):
        frame = group.sort_values("date").copy()
        close = frame["close"]
        volume = frame["volume"].replace(0, np.nan)

        # Return features: recent price momentum/reversal over 1 day, 1 week, and about 1 month.
        frame["ret_1d"] = close.pct_change(1)
        frame["ret_5d"] = close.pct_change(5)
        frame["ret_20d"] = close.pct_change(20)

        # Risk/state features: recent volatility, distance from moving averages, intraday range, abnormal volume.
        frame["vol_20d"] = frame["ret_1d"].rolling(20).std()
        frame["ma_gap_10d"] = close / close.rolling(10).mean() - 1.0
        frame["ma_gap_50d"] = close / close.rolling(50).mean() - 1.0
        frame["range_1d"] = (frame["high"] - frame["low"]) / close
        frame["volume_z_20d"] = (volume - volume.rolling(20).mean()) / volume.rolling(20).std()

        # Supervised-learning label: predict whether close is higher after horizon_days.
        # horizon_days=1 means "will the next trading day close higher than today's close?"
        frame["future_ret"] = close.shift(-horizon_days) / close - 1.0
        frame["target_up"] = (frame["future_ret"] > 0).astype(int)
        frame["symbol"] = symbol
        frames.append(frame)

    result = pd.concat(frames, ignore_index=True)
    result = result.replace([np.inf, -np.inf], np.nan)
    # Warm-up rows do not have enough history for rolling features such as ma_gap_50d.
    return result.dropna(subset=FEATURE_COLUMNS + ["future_ret", "target_up"]).reset_index(drop=True)
