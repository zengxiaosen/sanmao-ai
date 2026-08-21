from __future__ import annotations

import numpy as np
import pandas as pd


# regime.py —— 市场状态（regime）识别（P4）。
#
# 课题故事线：因子不是永远有效的，它的有效性随“市场状态”切换。
# 比如动量因子在单边牛市里好用，在高波动/急跌段容易失效。
# 这个模块做两件事：
#   1. detect_regimes：把每一天标成四种状态之一（规则可解释，答辩好讲）。
#   2. factor_regime_performance：统计每个因子在每种状态下的表现（beta / |t|），
#      直接支撑“因子在不同 regime 下有效性变化”的展示。
#
# 状态定义（优先级从上到下）：
#   high_vol 高波动：VIX >= vix_threshold（没有 VIX 时用自身波动率的 80 分位兜底）
#   bull 上行：      过去 trend_window 日收益 >= +trend_threshold
#   bear 下行：      过去 trend_window 日收益 <= -trend_threshold
#   sideways 震荡：  其余


REGIME_LABELS = ["high_vol 高波动", "bull 上行", "bear 下行", "sideways 震荡"]


def detect_regimes(
    price_features: pd.DataFrame,
    macro_features: pd.DataFrame | None = None,
    trend_window: int = 60,
    trend_threshold: float = 0.08,
    vix_threshold: float = 25.0,
) -> pd.DataFrame:
    """按日标注市场状态。

    输入：
        price_features：build_price_features 的输出（单资产，含 date/close/vol_20d）。
        macro_features：build_macro_features 的输出（可选，用里面的 vix_level）。
    输出：
        [date, ret_trend, vol_20d, vix_level, regime]
    """
    frame = price_features.sort_values("date").copy()
    if "symbol" in frame.columns and frame["symbol"].nunique() > 1:
        # 单资产课题：多股票时取第一只，避免语义不清。
        first = frame["symbol"].iloc[0]
        frame = frame[frame["symbol"] == first]

    out = pd.DataFrame({"date": pd.to_datetime(frame["date"]).values})
    out["ret_trend"] = frame["close"].pct_change(trend_window).values
    out["vol_20d"] = pd.to_numeric(frame.get("vol_20d"), errors="coerce").values

    # 优先用真实 VIX；没有宏观数据时用自身 20 日波动率的 80 分位当“高波动”阈值。
    if macro_features is not None and not macro_features.empty and "vix_level" in macro_features.columns:
        vix = macro_features[["date", "vix_level"]].copy()
        vix["date"] = pd.to_datetime(vix["date"])
        out = out.merge(vix, on="date", how="left")
        out["vix_level"] = out["vix_level"].ffill()
    else:
        out["vix_level"] = np.nan

    vol_cut = out["vol_20d"].quantile(0.8)

    def label(row: pd.Series) -> str:
        vix_level = row["vix_level"]
        high_vol = (vix_level >= vix_threshold) if np.isfinite(vix_level) else (
            np.isfinite(row["vol_20d"]) and np.isfinite(vol_cut) and row["vol_20d"] >= vol_cut
        )
        if high_vol:
            return "high_vol 高波动"
        trend = row["ret_trend"]
        if not np.isfinite(trend):
            return "sideways 震荡"
        if trend >= trend_threshold:
            return "bull 上行"
        if trend <= -trend_threshold:
            return "bear 下行"
        return "sideways 震荡"

    out["regime"] = out.apply(label, axis=1)
    out["ret_trend"] = out["ret_trend"].round(6)
    out["vol_20d"] = out["vol_20d"].round(6)
    return out.reset_index(drop=True)


def factor_regime_performance(betas: pd.DataFrame, regimes: pd.DataFrame) -> pd.DataFrame:
    """统计每个因子在每种市场状态下的平均 beta 和显著性 |t|。

    输入：
        betas：rolling_factor_betas 的输出 [date, factor, beta, tstat]。
        regimes：detect_regimes 的输出 [date, regime, ...]。
    输出：
        [regime, factor, mean_beta, mean_abs_t, days]
        mean_abs_t 越大表示该因子在该状态下和未来收益的关系越可信。
    """
    if betas.empty or regimes.empty:
        return pd.DataFrame(columns=["regime", "factor", "mean_beta", "mean_abs_t", "days"])

    b = betas.copy()
    b["date"] = pd.to_datetime(b["date"])
    r = regimes[["date", "regime"]].copy()
    r["date"] = pd.to_datetime(r["date"])
    merged = b.merge(r, on="date", how="inner")
    if merged.empty:
        return pd.DataFrame(columns=["regime", "factor", "mean_beta", "mean_abs_t", "days"])

    grouped = merged.groupby(["regime", "factor"]).agg(
        mean_beta=("beta", "mean"),
        mean_abs_t=("tstat", lambda s: float(np.mean(np.abs(s)))),
        days=("date", "nunique"),
    ).reset_index()
    grouped["mean_beta"] = grouped["mean_beta"].round(8)
    grouped["mean_abs_t"] = grouped["mean_abs_t"].round(4)
    return grouped.sort_values(["regime", "mean_abs_t"], ascending=[True, False]).reset_index(drop=True)
