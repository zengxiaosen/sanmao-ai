from __future__ import annotations

import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from quant_api import artifacts


# main.py —— FastAPI 应用入口。
#
# 启动：SANMAO_CONFIG=config/nvda_single_asset.yaml python scripts/run/serve_api.py
# 看板（Angular，:4200）通过下面这些接口拿数据。
#
# 设计原则：只读、不算。所有数字都来自 run_baseline.py 的产物（PG 表或 parquet）。

app = FastAPI(title="Sanmao Quant Dashboard API", version="0.1.0")

# 允许 Angular 开发服务器（:4200）跨域访问本后端（:8000）。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200", "http://127.0.0.1:4200"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    """健康检查：返回当前服务的策略、标的、产物是否就绪。"""
    ctx = artifacts.get_context()
    metrics = artifacts.load_metrics()
    return {
        "status": "ok",
        "strategy_id": ctx["strategy_id"],
        "symbols": ctx["symbols"],
        "config": ctx["config_path"],
        "has_metrics": bool(metrics),
        "has_predictions": len(artifacts.load_result("predictions", "predictions.parquet", limit=1)) > 0,
    }


@app.get("/factors")
def factors(limit: int = 60) -> dict:
    """因子库：返回每个因子的分组 + 最近若干天的值（给热力图）。

    limit 控制取最近多少个交易日。
    """
    tf = artifacts.load_training_features(limit=limit)
    if tf.empty:
        return {"factors": [], "dates": [], "matrix": [], "groups": {}}

    all_factor_cols = [c for group in artifacts.FACTOR_GROUPS.values() for c in group]
    present = [c for c in all_factor_cols if c in tf.columns]

    dates = pd.to_datetime(tf["date"]).dt.strftime("%Y-%m-%d").tolist()
    # 每个因子做 z-score 归一，让不同量纲的因子在热力图上可比。
    matrix = []
    for col in present:
        series = pd.to_numeric(tf[col], errors="coerce").fillna(0.0)
        std = series.std()
        z = (series - series.mean()) / std if std > 1e-9 else series * 0.0
        matrix.append({
            "factor": col,
            "group": artifacts.factor_group_of(col),
            "values": [round(float(v), 4) for v in z.tolist()],
            "latest": round(float(series.iloc[-1]), 6),
        })
    groups = {g: [c for c in cols if c in present] for g, cols in artifacts.FACTOR_GROUPS.items()}
    return {"factors": present, "dates": dates, "matrix": matrix, "groups": groups}


@app.get("/signals")
def signals(limit: int = 250) -> dict:
    """交易信号：K 线（close）+ 模型上涨概率 prob_up + 多空仓位。"""
    rows = artifacts.load_result("backtest_positions", "backtest_positions.parquet")
    if not rows:
        rows = artifacts.load_result("predictions", "predictions.parquet")
    rows = rows[-limit:] if limit else rows
    latest = rows[-1] if rows else {}
    # 用最新一行给一个直观的“今日建议”
    action = "flat 空仓"
    if latest:
        pos = latest.get("position", 1.0 if latest.get("prob_up", 0) >= 0.55 else 0.0)
        action = "long 持有" if pos and pos > 0 else "flat 空仓"
    return {"rows": rows, "latest": latest, "action": action}


@app.get("/backtest")
def backtest(limit: int = 2000) -> dict:
    """回测：资金曲线 equity + 回撤 drawdown + 汇总指标（sharpe/回撤/胜率等）。"""
    daily = artifacts.load_result("backtest_daily", "backtest_daily.parquet")
    daily = daily[-limit:] if limit else daily
    metrics = artifacts.load_metrics()
    return {
        "daily": daily,
        "summary": metrics.get("backtest", {}),
        "fold_metrics": metrics.get("fold_metrics", []),
        "feature_columns": metrics.get("feature_columns", []),
    }


@app.get("/factor-analytics")
def factor_analytics() -> dict:
    """因子有效性分析（P3）：重要性时间线 + 滚动 beta/t + 失效检测 + 替换建议。"""
    return {
        "importance_timeline": artifacts.load_result("factor_importance_timeline", "factor_importance_timeline.parquet"),
        "decay": artifacts.load_result("factor_decay", "factor_decay.parquet"),
        "replacements": artifacts.load_result("factor_replacements", "factor_replacements.parquet"),
        "attribution": artifacts.load_result("return_attribution", "return_attribution.parquet", limit=2000),
    }


@app.get("/regime")
def regime() -> dict:
    """市场状态（P4）：每日状态时间线 + 各因子在不同状态下的表现。"""
    return {
        "timeline": artifacts.load_result("regime_timeline", "regime_timeline.parquet"),
        "factor_performance": artifacts.load_result("factor_regime_performance", "factor_regime_performance.parquet"),
    }


@app.get("/review")
def review() -> dict:
    """自动复盘（P4）：run_baseline 生成的 review.json，直接透传给看板。"""
    return artifacts.load_json_artifact("review.json")
