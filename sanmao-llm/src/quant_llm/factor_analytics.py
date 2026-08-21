from __future__ import annotations

import numpy as np
import pandas as pd

from quant_llm.modeling import WalkForwardConfig, make_classifier


# factor_analytics.py —— 因子有效性分析（课题 AI 工作流的核心，评分权重最大）。
#
# 它回答四个问题：
#   1. 每个因子，模型当前有多看重它？（factor_importance_timeline —— 重要性随时间变化）
#   2. 每个因子，和未来收益的关系有多强、还成立吗？（rolling_factor_betas —— 滚动回归）
#   3. 策略赚/亏的钱，是哪些因子贡献的？（return_attribution —— 收益归因）
#   4. 哪些因子正在失效？拿什么替换？（detect_factor_decay + suggest_replacements —— 失效预警）
#
# 这些都是“打开黑盒”：模型不再是一个只吐 prob_up 的盒子，
# 而是能告诉你它依赖什么、什么在失灵。这正是机构级投研看板的价值。


def factor_importance_timeline(
    features: pd.DataFrame,
    config: WalkForwardConfig,
    model_config: dict,
    feature_columns: list[str],
) -> pd.DataFrame:
    """因子重要性时间线。

    做法（复用 walk-forward 的滚动窗口）：
        在每个训练窗口上训练一个 XGBoost，读它的 feature_importances_
        （每个因子对预测的贡献占比），记下这个窗口结束时的重要性。
        窗口向前滚动，就得到“每个因子的重要性怎么随时间变化”。

    返回长表：[window_end, factor, importance]（importance 已归一到和为 1）。

    典型故事：在 AI 行情段，情绪/宏观因子的 importance 上升，纯动量下降。
    """
    frame = features.sort_values("date").reset_index(drop=True)
    unique_dates = pd.Series(frame["date"].sort_values().unique())
    rows: list[dict] = []

    start_index = config.train_window_days
    while start_index < len(unique_dates):
        train_start = unique_dates.iloc[max(0, start_index - config.train_window_days)]
        train_end = unique_dates.iloc[start_index - 1]
        train = frame[(frame["date"] >= train_start) & (frame["date"] <= train_end)]
        if len(train) < config.min_train_rows:
            start_index += config.test_window_days
            continue

        model = make_classifier(model_config)
        model.fit(train[feature_columns], train["target_up"])

        # 不同模型读重要性的属性名不同，做个兼容。
        importances = getattr(model, "feature_importances_", None)
        if importances is None:
            start_index += config.test_window_days
            continue

        total = float(np.sum(importances)) or 1.0
        for factor, imp in zip(feature_columns, importances):
            rows.append({
                "window_end": pd.Timestamp(train_end).date().isoformat(),
                "factor": factor,
                "importance": round(float(imp) / total, 6),
            })
        start_index += config.test_window_days

    return pd.DataFrame(rows, columns=["window_end", "factor", "importance"])


def rolling_factor_betas(
    features: pd.DataFrame,
    feature_columns: list[str],
    window: int = 60,
) -> pd.DataFrame:
    """滚动单因子回归，算每个因子对未来收益的 beta 和 t 值。

    对每个因子，在最近 window 天的数据上做一元线性回归：
        future_ret ≈ alpha + beta * factor
    beta 表示“这个因子每高 1 个单位，未来收益平均多多少”；
    t 值表示这个关系“有多可信”（|t| 越大越显著）。

    用 numpy 的最小二乘（lstsq）手算，不引入 statsmodels，保持依赖精简。
    返回长表：[date, factor, beta, tstat]。
    """
    frame = features.sort_values("date").reset_index(drop=True)
    y_all = pd.to_numeric(frame["future_ret"], errors="coerce")
    rows: list[dict] = []

    for factor in feature_columns:
        x_all = pd.to_numeric(frame[factor], errors="coerce")
        # 逐日滚动：用过去 window 行拟合，记在当前日期上。
        for end in range(window, len(frame) + 1):
            sl = slice(end - window, end)
            x = x_all.iloc[sl].to_numpy()
            y = y_all.iloc[sl].to_numpy()
            mask = np.isfinite(x) & np.isfinite(y)
            if mask.sum() < window // 2 or np.nanstd(x[mask]) < 1e-12:
                continue
            xm, ym = x[mask], y[mask]
            # 设计矩阵 [1, x]，最小二乘解出 [alpha, beta]。
            A = np.column_stack([np.ones_like(xm), xm])
            coef, *_ = np.linalg.lstsq(A, ym, rcond=None)
            beta = float(coef[1])
            # 残差标准误 -> beta 的 t 值。
            resid = ym - A @ coef
            dof = max(len(ym) - 2, 1)
            sigma2 = float(resid @ resid) / dof
            sxx = float(((xm - xm.mean()) ** 2).sum()) or 1e-12
            se = np.sqrt(sigma2 / sxx) if sigma2 > 0 else 1e-12
            tstat = beta / se if se > 0 else 0.0
            rows.append({
                "date": pd.Timestamp(frame["date"].iloc[end - 1]).date().isoformat(),
                "factor": factor,
                "beta": round(beta, 8),
                "tstat": round(float(tstat), 4),
            })

    return pd.DataFrame(rows, columns=["date", "factor", "beta", "tstat"])


def detect_factor_decay(
    importance_timeline: pd.DataFrame,
    betas: pd.DataFrame,
    coverage: dict[str, float] | None = None,
    sparse_threshold: float = 0.05,
) -> pd.DataFrame:
    """因子失效检测。

    综合两个信号判断每个因子的健康状态：
        - importance 趋势：最近一段比早期明显下降 -> 在“退场”。
        - |t 值|：最近显著性坍缩（接近 0）-> 和收益的关系不再可信。

    coverage 是每个因子的“非零天数占比”（0~1）。事件类因子（如公告计数）
    大部分日子天然是 0，样本太稀疏时 beta/t 全是噪声——这种因子不能下
    “衰退/失效”结论，只能标成 sparse（数据稀疏），否则结论是自欺欺人。

    输出每个因子一行：[factor, status, recent_importance, importance_trend, recent_abs_t, coverage]
        status ∈ active（健康）/ decaying（衰退中）/ failed（已失效）/ sparse（数据稀疏，不判定）。
    """
    coverage = coverage or {}
    rows: list[dict] = []
    factors = sorted(set(importance_timeline["factor"]) | set(betas["factor"])) if not importance_timeline.empty else []

    for factor in factors:
        imp = importance_timeline[importance_timeline["factor"] == factor].sort_values("window_end")
        recent_imp = float(imp["importance"].tail(3).mean()) if not imp.empty else 0.0
        early_imp = float(imp["importance"].head(3).mean()) if len(imp) >= 3 else recent_imp
        trend = recent_imp - early_imp  # 负=重要性在下降

        bt = betas[betas["factor"] == factor].sort_values("date")
        recent_abs_t = float(bt["tstat"].abs().tail(20).mean()) if not bt.empty else 0.0

        cov = float(coverage.get(factor, 1.0))

        # 阈值说明（答辩可讲）：
        #   日频单因子滚动回归的 |t| 天然偏低（市场接近有效，|t|≈1 已算有信息），
        #   所以不能只凭 |t| 低就说“衰退”——那会把所有因子都打成衰退，结论失真。
        #   这里要求“模型权重在下滑”与“统计关系变弱”同时成立才降级：
        #     failed   : 权重大幅下滑(>2pp) 且 关系基本消失(|t|<0.6)
        #     decaying : 权重在下滑(>1pp)   且 关系偏弱(|t|<1.0)
        #     active   : 其余（权重稳定，或关系仍然可信）
        if cov < sparse_threshold:
            # 非零样本太少：统计上判断不了衰退与否，诚实标“数据稀疏”。
            status = "sparse"
        elif trend < -0.02 and recent_abs_t < 0.6:
            status = "failed"
        elif trend < -0.01 and recent_abs_t < 1.0:
            status = "decaying"
        else:
            status = "active"

        rows.append({
            "factor": factor,
            "status": status,
            "recent_importance": round(recent_imp, 6),
            "importance_trend": round(trend, 6),
            "recent_abs_t": round(recent_abs_t, 4),
            "coverage": round(cov, 4),
        })

    return pd.DataFrame(rows, columns=["factor", "status", "recent_importance", "importance_trend", "recent_abs_t", "coverage"])


def suggest_replacements(
    decay_table: pd.DataFrame,
    factor_groups: dict[str, list[str]],
) -> pd.DataFrame:
    """给失效/衰退的因子推荐替换。

    规则：从“同一大类”（量价/宏观/舆情）里挑一个当前 active 且重要性最高的因子作替代。
    这体现课题要的“因子失效后自动替换”，且替换在同类里选，逻辑可解释。
    sparse（数据稀疏）因子不参与：既不算失效、也不能当替代品。

    返回：[failed_factor, group, replacement, replacement_importance]。
    """
    # 因子 -> 大类
    factor_to_group: dict[str, str] = {}
    for group, cols in factor_groups.items():
        for c in cols:
            factor_to_group[c] = group

    active = decay_table[decay_table["status"] == "active"]
    rows: list[dict] = []
    for _, r in decay_table[~decay_table["status"].isin(["active", "sparse"])].iterrows():
        factor = r["factor"]
        group = factor_to_group.get(factor, "其他 other")
        peers = active[active["factor"].map(lambda f: factor_to_group.get(f, "其他 other") == group)]
        if peers.empty:
            replacement, imp = None, None
        else:
            best = peers.sort_values("recent_importance", ascending=False).iloc[0]
            replacement, imp = best["factor"], round(float(best["recent_importance"]), 6)
        rows.append({
            "failed_factor": factor,
            "group": group,
            "replacement": replacement,
            "replacement_importance": imp,
        })

    return pd.DataFrame(rows, columns=["failed_factor", "group", "replacement", "replacement_importance"])


def return_attribution(
    predictions: pd.DataFrame,
    features: pd.DataFrame,
    betas: pd.DataFrame,
    feature_columns: list[str],
) -> pd.DataFrame:
    """收益归因（简化版）：把每天的收益按“因子暴露 × 因子 beta”拆分贡献。

    做法：取每个因子最近的平均 beta，乘以当天该因子的标准化取值（暴露），
    得到该因子当天对预期收益的“贡献分量”。这是一个可解释的近似，
    用来在看板上展示“今天的信号里，哪个因子在推、哪个在拖”。

    返回长表：[date, factor, contribution]。
    """
    if betas.empty or features.empty:
        return pd.DataFrame(columns=["date", "factor", "contribution"])

    # 每个因子取最近 beta 均值作为代表暴露系数。
    latest_beta = betas.groupby("factor")["beta"].apply(lambda s: float(s.tail(20).mean())).to_dict()

    frame = features.sort_values("date").copy()
    rows: list[dict] = []
    for factor in feature_columns:
        beta = latest_beta.get(factor, 0.0)
        if beta == 0.0:
            continue
        x = pd.to_numeric(frame[factor], errors="coerce")
        std = x.std()
        z = (x - x.mean()) / std if std and std > 1e-9 else x * 0.0
        contrib = z * beta
        for d, c in zip(frame["date"], contrib):
            if np.isfinite(c):
                rows.append({
                    "date": pd.Timestamp(d).date().isoformat(),
                    "factor": factor,
                    "contribution": round(float(c), 8),
                })

    return pd.DataFrame(rows, columns=["date", "factor", "contribution"])
