from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd


# review.py —— 自动复盘报告（P4）。
#
# 每次 run_baseline 跑完，把“这次实验发生了什么”浓缩成一份人能直接读的复盘：
#   - 当前市场状态是什么、最近 90 天各状态占比
#   - 回测赚了多少、回撤多少
#   - 模型现在最依赖哪些因子
#   - 哪些因子在衰退/失效、建议用什么替换
#   - 最新一天的信号是什么
# 产物：report_dir/review.json（给看板）+ review.md（给人看/贴周报）。
# 全部是规则生成的中文结论，不调用 LLM，保证可复现、零成本。


def _regime_distribution(regimes: pd.DataFrame, recent_days: int = 90) -> dict:
    if regimes is None or regimes.empty:
        return {}
    tail = regimes.sort_values("date").tail(recent_days)
    counts = tail["regime"].value_counts(normalize=True)
    return {str(k): round(float(v), 4) for k, v in counts.items()}


def build_review(
    backtest_summary: dict,
    decay_table: pd.DataFrame | None,
    replacements: pd.DataFrame | None,
    regimes: pd.DataFrame | None,
    latest_signal: dict | None,
    importance_timeline: pd.DataFrame | None,
    data_range: tuple[str, str] | None = None,
) -> dict:
    """汇总一份结构化复盘。所有输入都允许为空，缺什么就少说什么。"""
    review: dict = {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "data_range": {"start": data_range[0], "end": data_range[1]} if data_range else {},
        "backtest": backtest_summary or {},
    }

    # 当前市场状态 + 最近分布
    if regimes is not None and not regimes.empty:
        last = regimes.sort_values("date").iloc[-1]
        review["regime"] = {
            "latest": str(last["regime"]),
            "latest_date": pd.Timestamp(last["date"]).date().isoformat(),
            "recent_distribution": _regime_distribution(regimes),
        }

    # 模型最近最依赖的因子（重要性时间线最后一个窗口的 top5）
    if importance_timeline is not None and not importance_timeline.empty:
        last_window = importance_timeline["window_end"].max()
        top = (
            importance_timeline[importance_timeline["window_end"] == last_window]
            .sort_values("importance", ascending=False)
            .head(5)
        )
        review["top_factors"] = [
            {"factor": r["factor"], "importance": float(r["importance"])} for _, r in top.iterrows()
        ]

    # 因子健康度：统计 + 衰退/失效清单 + 替换建议
    if decay_table is not None and not decay_table.empty:
        status_counts = decay_table["status"].value_counts()
        judged = decay_table[decay_table["status"] != "sparse"]
        review["factor_health"] = {
            "active": int(status_counts.get("active", 0)),
            "decaying": int(status_counts.get("decaying", 0)),
            "failed": int(status_counts.get("failed", 0)),
            "sparse": int(status_counts.get("sparse", 0)),
            "unhealthy_factors": judged[~judged["status"].isin(["active"])]["factor"].tolist(),
        }
    if replacements is not None and not replacements.empty:
        review["replacements"] = [
            {
                "failed_factor": r["failed_factor"],
                "replacement": r["replacement"],
                "group": r["group"],
            }
            for _, r in replacements.iterrows()
            # 注意用 pd.notna：replacement 经 parquet 落盘后 None 会变 NaN，
            # `is not None` 拦不住，会在复盘里输出“可用 nan 顶上”的怪话。
            if pd.notna(r["replacement"])
        ]

    if latest_signal:
        review["latest_signal"] = latest_signal

    review["narrative"] = _narrative(review)
    return review


def _narrative(review: dict) -> list[str]:
    """把结构化复盘翻译成几句人话（规则模板，非 LLM）。"""
    lines: list[str] = []

    regime = review.get("regime", {})
    if regime:
        lines.append(f"当前市场状态：{regime['latest']}（截至 {regime['latest_date']}）。")

    backtest = review.get("backtest", {})
    if backtest:
        annual = backtest.get("annual_return")
        sharpe = backtest.get("sharpe")
        drawdown = backtest.get("max_drawdown")
        parts = []
        if annual is not None:
            parts.append(f"年化收益 {annual * 100:.1f}%")
        if sharpe is not None:
            parts.append(f"Sharpe {sharpe:.2f}")
        if drawdown is not None:
            parts.append(f"最大回撤 {drawdown * 100:.1f}%")
        if parts:
            lines.append("回测表现：" + "，".join(parts) + "。")

    top = review.get("top_factors", [])
    if top:
        names = "、".join(t["factor"] for t in top[:3])
        lines.append(f"模型当前最依赖的因子：{names}。")

    health = review.get("factor_health", {})
    if health:
        unhealthy = health.get("unhealthy_factors", [])
        sparse = health.get("sparse", 0)
        sparse_text = f"，另有 {sparse} 个事件类因子数据稀疏暂不判定" if sparse else ""
        if unhealthy:
            lines.append(
                f"因子体检：{health['active']} 个健康，"
                f"{health['decaying']} 个衰退中，{health['failed']} 个已失效"
                f"（关注：{'、'.join(unhealthy[:4])}）{sparse_text}。"
            )
        else:
            lines.append(f"因子体检：全部 {health['active']} 个可判定因子状态健康{sparse_text}。")

    for rep in review.get("replacements", [])[:3]:
        lines.append(f"替换建议：{rep['failed_factor']} 走弱，可用同类的 {rep['replacement']} 顶上。")

    signal = review.get("latest_signal", {})
    if signal:
        action = signal.get("action", "")
        prob = signal.get("prob_up")
        prob_text = f"（上涨概率 {prob:.2f}）" if isinstance(prob, (int, float)) else ""
        lines.append(f"最新信号（{signal.get('date', '')}）：{action}{prob_text}。")

    return lines


def render_review_markdown(review: dict) -> str:
    """把复盘 JSON 渲染成 markdown，直接可读/可贴周报。"""
    lines = ["# 策略复盘报告", ""]
    lines.append(f"生成时间：{review.get('generated_at', '')}")
    data_range = review.get("data_range", {})
    if data_range:
        lines.append(f"数据区间：{data_range.get('start', '')} ~ {data_range.get('end', '')}")
    lines.append("")

    lines.append("## 结论速读")
    lines.append("")
    for sentence in review.get("narrative", []):
        lines.append(f"- {sentence}")
    lines.append("")

    dist = review.get("regime", {}).get("recent_distribution", {})
    if dist:
        lines.append("## 最近 90 天市场状态分布")
        lines.append("")
        for regime_name, ratio in sorted(dist.items(), key=lambda kv: -kv[1]):
            lines.append(f"- {regime_name}: {ratio * 100:.0f}%")
        lines.append("")

    top = review.get("top_factors", [])
    if top:
        lines.append("## 模型当前最依赖的因子")
        lines.append("")
        for t in top:
            lines.append(f"- {t['factor']}: importance {t['importance']:.3f}")
        lines.append("")

    return "\n".join(lines)
