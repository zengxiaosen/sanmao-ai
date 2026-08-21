from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

import pandas as pd

from quant_llm.config import load_config, load_project_env
from quant_llm import db


# artifacts.py —— 看板后端的“数据读取层”。
#
# 它回答一个问题：某个策略的结果（预测/回测/因子）在哪、怎么读成 JSON。
#
# 读取优先级：
#   1. 先试 PostgreSQL（run_baseline 跑完会同步进去，能存多次运行）。
#   2. PG 没有就回退读 report_dir / data_dir 下的 parquet / json 文件。
# 这样即使没配数据库，看板也能靠文件跑起来。


def _which_config() -> str:
    """看板服务哪个策略，由环境变量 SANMAO_CONFIG 指定（一个 YAML 路径）。"""
    return os.environ.get("SANMAO_CONFIG", "config/nvda_single_asset.yaml")


@lru_cache(maxsize=1)
def get_context() -> dict:
    """加载并缓存当前策略的上下文：config、strategy_id、各产物目录。"""
    load_project_env()
    config_path = _which_config()
    config = load_config(config_path)
    strategy_id = str(config["strategy_id"])
    return {
        "config_path": config_path,
        "config": config,
        "strategy_id": strategy_id,
        "data_dir": Path(config["data_dir"]),
        "report_dir": Path(config["report_dir"]),
        "symbols": config.get("symbols", []),
    }


def _engine_or_none():
    """有 DATABASE_URL 就返回 engine，否则返回 None（走文件回退）。"""
    if not db.get_database_url():
        return None
    try:
        return db.make_engine()
    except Exception:
        return None


def _records(df: pd.DataFrame) -> list[dict]:
    """把 DataFrame 转成前端友好的 records，时间戳转成 ISO 日期字符串。"""
    if df is None or df.empty:
        return []
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%Y-%m-%d")
    # 去掉内部辅助列，前端用不到
    out = out.drop(columns=[c for c in ["strategy_id"] if c in out.columns])
    return json.loads(out.to_json(orient="records"))


def load_result(table: str, parquet_name: str, limit: int | None = None) -> list[dict]:
    """读一张结果表：先试 PG 的 quant_<table>，回退 report_dir/<parquet_name>。"""
    ctx = get_context()
    engine = _engine_or_none()
    if engine is not None:
        df = db.read_table(table, strategy_id=ctx["strategy_id"], engine=engine, limit=limit)
        if not df.empty:
            return _records(df)
    # 文件回退
    path = ctx["report_dir"] / parquet_name
    if path.exists():
        df = pd.read_parquet(path)
        if limit:
            df = df.tail(limit)
        return _records(df)
    return []


def load_training_features(limit: int | None = None) -> pd.DataFrame:
    """读训练特征表（因子的原始值），只走文件（这张表不同步进 PG）。"""
    ctx = get_context()
    path = ctx["data_dir"] / "features" / "training_features.parquet"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path)
    return df.tail(limit) if limit else df


def load_metrics() -> dict:
    """读 metrics.json（模型指标 + 回测汇总指标）。"""
    ctx = get_context()
    path = ctx["report_dir"] / "metrics.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_json_artifact(filename: str) -> dict:
    """读 report_dir 下的任意 json 产物（例如 review.json）。不存在返回 {}。"""
    ctx = get_context()
    path = ctx["report_dir"] / filename
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


# 因子分组：把每个因子归到 量价 / 舆情 / 宏观 三大类，供热力图分组展示。
# 宏观因子（macro_*）在 P2 才会出现，先预留。
FACTOR_GROUPS = {
    "量价 price-volume": [
        "ret_1d", "ret_5d", "ret_20d", "vol_20d",
        "ma_gap_10d", "ma_gap_50d", "range_1d", "volume_z_20d",
    ],
    "舆情 sentiment": [
        "llm_news_count", "llm_mean_sentiment", "llm_weighted_sentiment",
        "llm_max_confidence", "event_earnings_count", "event_macro_count",
        "risk_margin_pressure_count", "risk_guidance_weak_count", "risk_supply_chain_count",
    ],
    "宏观 macro": [
        "vix_level", "vix_change_5d", "ust10y_level", "ust10y_change_5d",
        "dxy_change_5d", "fedfunds_level", "yield_curve_10y2y",
    ],
}


def factor_group_of(name: str) -> str:
    for group, cols in FACTOR_GROUPS.items():
        if name in cols:
            return group
    return "其他 other"
