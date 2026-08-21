from __future__ import annotations

import numpy as np
import pandas as pd

from quant_llm.modeling import WalkForwardConfig
from quant_llm.factor_analytics import (
    factor_importance_timeline,
    rolling_factor_betas,
    detect_factor_decay,
    suggest_replacements,
    return_attribution,
)


def _synthetic_features(n: int = 400) -> tuple[pd.DataFrame, list[str]]:
    """造一份带信号的合成训练数据：f_good 真的能预测涨跌，f_noise 是纯噪声。"""
    rng = np.random.default_rng(0)
    dates = pd.bdate_range("2021-01-01", periods=n)
    f_good = rng.normal(0, 1, n)
    f_noise = rng.normal(0, 1, n)
    # 未来收益主要由 f_good 决定（加点噪声）。
    future_ret = 0.01 * f_good + rng.normal(0, 0.005, n)
    df = pd.DataFrame({
        "date": dates,
        "symbol": "TEST.US",
        "close": 100 + np.cumsum(rng.normal(0, 1, n)),
        "f_good": f_good,
        "f_noise": f_noise,
        "future_ret": future_ret,
        "target_up": (future_ret > 0).astype(int),
    })
    return df, ["f_good", "f_noise"]


def test_importance_timeline_ranks_signal_above_noise() -> None:
    df, cols = _synthetic_features()
    cfg = WalkForwardConfig(train_window_days=120, test_window_days=40, min_train_rows=50)
    timeline = factor_importance_timeline(df, cfg, {"kind": "xgboost"}, cols)
    assert not timeline.empty
    assert set(timeline.columns) == {"window_end", "factor", "importance"}
    # 平均来看，真信号因子的重要性应高于噪声因子。
    mean_imp = timeline.groupby("factor")["importance"].mean()
    assert mean_imp["f_good"] > mean_imp["f_noise"]


def test_rolling_betas_signal_more_significant() -> None:
    df, cols = _synthetic_features()
    betas = rolling_factor_betas(df, cols, window=60)
    assert not betas.empty
    assert set(betas.columns) == {"date", "factor", "beta", "tstat"}
    # 真信号因子的 |t| 平均应更大（关系更显著）。
    mean_abs_t = betas.assign(abs_t=betas["tstat"].abs()).groupby("factor")["abs_t"].mean()
    assert mean_abs_t["f_good"] > mean_abs_t["f_noise"]


def test_decay_and_replacement_flow() -> None:
    df, cols = _synthetic_features()
    cfg = WalkForwardConfig(train_window_days=120, test_window_days=40, min_train_rows=50)
    timeline = factor_importance_timeline(df, cfg, {"kind": "xgboost"}, cols)
    betas = rolling_factor_betas(df, cols, window=60)
    decay = detect_factor_decay(timeline, betas)
    assert set(decay.columns) == {"factor", "status", "recent_importance", "importance_trend", "recent_abs_t", "coverage"}
    assert set(decay["status"]).issubset({"active", "decaying", "failed", "sparse"})

    groups = {"g": ["f_good", "f_noise"]}
    repl = suggest_replacements(decay, groups)
    # 替换表结构正确（可能为空，取决于是否有失效因子）。
    assert set(repl.columns) == {"failed_factor", "group", "replacement", "replacement_importance"}


def test_sparse_factor_marked_not_judged() -> None:
    """事件类因子非零样本太少时，应标 sparse 而不是妄下 decaying/failed 结论。"""
    df, cols = _synthetic_features()
    cfg = WalkForwardConfig(train_window_days=120, test_window_days=40, min_train_rows=50)
    timeline = factor_importance_timeline(df, cfg, {"kind": "xgboost"}, cols)
    betas = rolling_factor_betas(df, cols, window=60)
    coverage = {"f_good": 1.0, "f_noise": 0.002}  # f_noise 假装是 0.2% 覆盖的事件因子
    decay = detect_factor_decay(timeline, betas, coverage=coverage)
    assert decay.set_index("factor").loc["f_noise", "status"] == "sparse"
    assert decay.set_index("factor").loc["f_good", "status"] != "sparse"
    # sparse 因子不应出现在替换建议里（不算失效，也不当替代品）
    repl = suggest_replacements(decay, {"g": cols})
    assert "f_noise" not in set(repl["failed_factor"])


def test_return_attribution_shape() -> None:
    df, cols = _synthetic_features()
    betas = rolling_factor_betas(df, cols, window=60)
    attr = return_attribution(df, df, betas, cols)
    assert set(attr.columns) == {"date", "factor", "contribution"}
