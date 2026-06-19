from __future__ import annotations

import numpy as np
import pandas as pd


def build_backtest_frames(
    predictions: pd.DataFrame,
    threshold: float,
    transaction_cost_bps: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """把模型预测转换成逐标的持仓和每日资金曲线。

    输入 predictions：
        walk-forward 预测结果，至少包含：
            date, symbol, future_ret, prob_up

    输出：
        frame:
            每只股票每天的 prob_up、position、strategy_ret。

        daily:
            每天组合层面的 strategy_ret、equity、drawdown。

    这一步就是“回测明细”。你想直观看收益，看 daily 里的 equity/strategy_ret。
    """
    frame = predictions.sort_values(["symbol", "date"]).copy()

    # position=1 means long/holding the stock; position=0 means flat/cash.
    # The model predicts prob_up. The strategy buys only when that probability clears the threshold.
    frame["position"] = (frame["prob_up"] >= threshold).astype(float)
    frame["prev_position"] = frame.groupby("symbol")["position"].shift(1).fillna(0.0)

    # Turnover is 1 when we switch flat->long or long->flat, and 0 when the position is unchanged.
    frame["turnover"] = (frame["position"] - frame["prev_position"]).abs()
    frame["cost"] = frame["turnover"] * transaction_cost_bps / 10_000.0

    # If long, earn next-period return. If flat, earn zero. Then subtract trading cost.
    frame["strategy_ret"] = frame["position"] * frame["future_ret"] - frame["cost"]

    # Equal-weight all symbols with available predictions on each date.
    daily = frame.groupby("date", as_index=False)["strategy_ret"].mean()
    returns = daily["strategy_ret"].to_numpy()
    if len(returns) == 0:
        raise ValueError("No returns available for backtest")

    # Equity curve: starting from 1.0, compound daily strategy returns.
    daily["equity"] = np.cumprod(1.0 + returns)
    daily["running_max"] = daily["equity"].cummax()
    daily["drawdown"] = daily["equity"] / daily["running_max"] - 1.0
    return frame, daily


def summarize_backtest(backtest_daily: pd.DataFrame, backtest_positions: pd.DataFrame) -> dict[str, float]:
    """从回测明细汇总成 metrics.json 里的指标。"""
    returns = backtest_daily["strategy_ret"].to_numpy()
    equity = backtest_daily["equity"].to_numpy()
    drawdown = backtest_daily["drawdown"].to_numpy()
    annual_return = equity[-1] ** (252 / len(returns)) - 1.0
    annual_vol = float(np.std(returns, ddof=1) * np.sqrt(252)) if len(returns) > 1 else 0.0
    sharpe = annual_return / annual_vol if annual_vol > 0 else 0.0

    return {
        "rows": float(len(backtest_positions)),
        "days": float(len(backtest_daily)),
        "total_return": float(equity[-1] - 1.0),
        "annual_return": float(annual_return),
        "annual_volatility": float(annual_vol),
        "sharpe": float(sharpe),
        "max_drawdown": float(drawdown.min()),
        "mean_daily_turnover": float(backtest_positions["turnover"].mean()),
        "hit_rate_when_in_market": float((backtest_positions.loc[backtest_positions["position"] > 0, "future_ret"] > 0).mean()),
        "exposure": float(backtest_positions["position"].mean()),
    }


def long_flat_backtest(predictions: pd.DataFrame, threshold: float, transaction_cost_bps: float) -> dict[str, float]:
    """兼容旧调用：只返回汇总指标。"""
    positions, daily = build_backtest_frames(predictions, threshold, transaction_cost_bps)
    return summarize_backtest(daily, positions)
