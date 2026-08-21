from __future__ import annotations

import os
from pathlib import Path

import pandas as pd


# 这个模块负责把量化结果写进 PostgreSQL，并从 PostgreSQL 读回。
#
# 为什么需要它：
#   run_baseline.py 把结果存成 parquet 文件（快、适合批处理）。
#   但看板（FastAPI + Angular）需要一个能随时查询、能存历史的地方，
#   所以我们把关键结果同步一份进 PostgreSQL。
#
# 命名约定：
#   所有表都加 quant_ 前缀（quant_factors / quant_signals / quant_backtest_daily ...），
#   避免和 sanmao-api 已有的业务表（users/channels/logs...）冲突。
#
# 连接串来自环境变量 DATABASE_URL（放在 .env，不进 Git）：
#   postgresql+psycopg://user:password@host:5432/dbname

TABLE_PREFIX = "quant_"


def get_database_url() -> str | None:
    """读取 DATABASE_URL。没配置就返回 None（此时管线只写 parquet，不写库）。"""
    return os.environ.get("DATABASE_URL")


def make_engine(database_url: str | None = None):
    """创建 SQLAlchemy engine。

    把 sqlalchemy import 放在函数里，是因为只有真正要写库时才需要它，
    纯跑 parquet 回测不必强依赖数据库驱动。
    """
    from sqlalchemy import create_engine

    url = database_url or get_database_url()
    if not url:
        raise RuntimeError("DATABASE_URL not set; cannot connect to PostgreSQL")
    return create_engine(url)


def write_dataframe(
    df: pd.DataFrame,
    table: str,
    *,
    strategy_id: str,
    engine=None,
    if_exists: str = "replace",
) -> int:
    """把一个结果 DataFrame 写进 PostgreSQL 的 quant_<table> 表。

    参数：
        df: 要写入的结果表（例如 predictions、backtest_daily）。
        table: 逻辑表名，不含前缀。最终表名是 quant_<table>。
        strategy_id: 策略 ID。会作为一列写进去，这样同一张表里可以放多个策略的结果，
                     查询时用 WHERE strategy_id = '...' 区分。
        if_exists: 'replace' 覆盖（默认，适合每次重算全量覆盖），'append' 追加。

    返回：写入的行数。
    """
    if df is None or df.empty:
        return 0

    engine = engine or make_engine()
    out = df.copy()
    # 加一列 strategy_id，方便一表多策略共存。
    out.insert(0, "strategy_id", strategy_id)

    full_table = f"{TABLE_PREFIX}{table}"
    # 覆盖模式下，只删除本策略的旧行，不动别的策略数据。
    if if_exists == "replace":
        _delete_strategy_rows(engine, full_table, strategy_id)
        target_if_exists = "append"
    else:
        target_if_exists = if_exists

    out.to_sql(full_table, engine, if_exists=target_if_exists, index=False)
    return len(out)


def _delete_strategy_rows(engine, full_table: str, strategy_id: str) -> None:
    """删除某策略在某表的旧行；表不存在时静默跳过。"""
    from sqlalchemy import text

    with engine.begin() as conn:
        exists = conn.execute(
            text("SELECT to_regclass(:t)"),
            {"t": f"public.{full_table}"},
        ).scalar()
        if exists is None:
            return
        conn.execute(
            text(f"DELETE FROM {full_table} WHERE strategy_id = :sid"),
            {"sid": strategy_id},
        )


def read_table(
    table: str,
    *,
    strategy_id: str,
    engine=None,
    limit: int | None = None,
) -> pd.DataFrame:
    """从 quant_<table> 读回某策略的结果。表不存在时返回空 DataFrame。"""
    from sqlalchemy import text

    engine = engine or make_engine()
    full_table = f"{TABLE_PREFIX}{table}"
    with engine.begin() as conn:
        exists = conn.execute(
            text("SELECT to_regclass(:t)"),
            {"t": f"public.{full_table}"},
        ).scalar()
        if exists is None:
            return pd.DataFrame()
        sql = f"SELECT * FROM {full_table} WHERE strategy_id = :sid"
        if limit:
            sql += f" LIMIT {int(limit)}"
        return pd.read_sql(text(sql), conn, params={"sid": strategy_id})


def sync_parquet_dir(report_dir: str | Path, strategy_id: str, engine=None) -> dict[str, int]:
    """把一个 report_dir 里的关键 parquet 结果同步进 PostgreSQL。

    这是 run_baseline.py 跑完后调用的便捷入口：把 predictions / backtest_daily /
    backtest_positions 等结果一次性写库。返回 {表名: 写入行数}。
    """
    report_dir = Path(report_dir)
    engine = engine or make_engine()

    # 逻辑表名 -> parquet 文件名。只同步看板会用到的结果表。
    mapping = {
        "predictions": "predictions.parquet",
        "backtest_daily": "backtest_daily.parquet",
        "backtest_positions": "backtest_positions.parquet",
    }
    written: dict[str, int] = {}
    for table, filename in mapping.items():
        path = report_dir / filename
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        written[table] = write_dataframe(df, table, strategy_id=strategy_id, engine=engine)
    return written
