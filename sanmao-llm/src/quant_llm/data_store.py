"""市场数据持久化存储（PostgreSQL）

行情不该每次跑都重新下载：网络在国内本来就不稳，重复下载还会被上游限流。
这里把所有拉回来的日线落到 PostgreSQL，之后建模、回测、看板都从库里读。

表：
- quant_market_data  日线行情，主键 (symbol, date)
- quant_data_meta    每个标的的最后更新时间 / 行数 / 数据源

连接串优先级：显式传参 > 环境变量 SANMAO_PG_DSN > /opt/sanmao/sanmao-api/pg.env > 默认本机。
pg.env 里是 new-api 在用的同一个库，量化表统一加 quant_ 前缀，不会撞上业务表。
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from sqlalchemy import create_engine

DEFAULT_DSN = "postgresql://sanmao:sanmao123456@127.0.0.1:5432/sanmao"
PG_ENV_PATH = "/opt/sanmao/sanmao-api/pg.env"

MARKET_TABLE = "quant_market_data"
META_TABLE = "quant_data_meta"


def resolve_dsn(dsn: str | None = None) -> str:
    """找出该连哪个库。"""
    if dsn:
        return dsn
    env_dsn = os.environ.get("SANMAO_PG_DSN")
    if env_dsn:
        return env_dsn
    # new-api 的 pg.env 里有一份现成的连接串，直接复用，省得两处维护密码
    env_file = Path(PG_ENV_PATH)
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            match = re.match(r"^\s*(?:export\s+)?SQL_DSN\s*=\s*(.+?)\s*$", line)
            if match:
                value = match.group(1).strip().strip('"').strip("'")
                if value.startswith("postgres"):
                    return value
    return DEFAULT_DSN


class MarketDataStore:
    """市场数据存储（PostgreSQL 后端）"""

    def __init__(self, dsn: str | None = None):
        self.dsn = resolve_dsn(dsn)
        self._engine = None
        self._init_db()

    def _connect(self):
        return psycopg2.connect(self.dsn)

    @property
    def engine(self):
        """pandas 只认 SQLAlchemy connectable，读操作走这个。

        写操作仍用 psycopg2 —— execute_values 的批量插入快得多，
        没有理由为了统一而换掉。engine 懒加载，避免只写不读时白建连接池。
        """
        if self._engine is None:
            dsn = self.dsn.replace("postgresql://", "postgresql+psycopg2://", 1)
            self._engine = create_engine(dsn, pool_pre_ping=True)
        return self._engine

    def _init_db(self) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {MARKET_TABLE} (
                    symbol      TEXT   NOT NULL,
                    date        DATE   NOT NULL,
                    open        DOUBLE PRECISION NOT NULL,
                    high        DOUBLE PRECISION NOT NULL,
                    low         DOUBLE PRECISION NOT NULL,
                    close       DOUBLE PRECISION NOT NULL,
                    volume      BIGINT NOT NULL,
                    source      TEXT,
                    updated_at  TIMESTAMPTZ DEFAULT now(),
                    PRIMARY KEY (symbol, date)
                )
                """
            )
            # 按标的取区间是最常见的查询，单列 date 索引给「全市场某天截面」用
            cur.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{MARKET_TABLE}_date ON {MARKET_TABLE}(date)"
            )
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {META_TABLE} (
                    symbol      TEXT PRIMARY KEY,
                    last_update TIMESTAMPTZ NOT NULL,
                    row_count   INTEGER NOT NULL,
                    start_date  DATE,
                    end_date    DATE,
                    source      TEXT
                )
                """
            )
            conn.commit()

    def save_data(self, df: pd.DataFrame, source: str | None = None, replace: bool = True) -> int:
        """写入行情。

        Args:
            df: 需含 [symbol, date, open, high, low, close, volume]
            source: 数据源标记（tencent / yfinance / …），便于日后排查数据打架
            replace: True=同一天的数据以新的为准；False=已存在就跳过
        Returns:
            实际写入/更新的行数
        """
        if df is None or df.empty:
            return 0

        required = ["symbol", "date", "open", "high", "low", "close", "volume"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"缺少列: {missing}")

        frame = df[required].copy()
        frame["date"] = pd.to_datetime(frame["date"]).dt.date
        for col in ("open", "high", "low", "close"):
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
        frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce").fillna(0).astype("int64")
        frame = frame.dropna(subset=["open", "high", "low", "close"])
        if frame.empty:
            return 0
        frame["source"] = source

        conflict = (
            """ON CONFLICT (symbol, date) DO UPDATE SET
                   open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
                   close=EXCLUDED.close, volume=EXCLUDED.volume,
                   source=COALESCE(EXCLUDED.source, {t}.source), updated_at=now()"""
            .format(t=MARKET_TABLE)
            if replace
            else "ON CONFLICT (symbol, date) DO NOTHING"
        )

        rows = list(frame.itertuples(index=False, name=None))
        with self._connect() as conn, conn.cursor() as cur:
            execute_values(
                cur,
                f"INSERT INTO {MARKET_TABLE} (symbol,date,open,high,low,close,volume,source) VALUES %s {conflict}",
                rows,
                page_size=1000,
            )
            written = cur.rowcount
            for symbol, group in frame.groupby("symbol"):
                cur.execute(
                    f"""
                    INSERT INTO {META_TABLE} (symbol,last_update,row_count,start_date,end_date,source)
                    SELECT %s, %s,
                           (SELECT COUNT(*) FROM {MARKET_TABLE} WHERE symbol=%s),
                           (SELECT MIN(date) FROM {MARKET_TABLE} WHERE symbol=%s),
                           (SELECT MAX(date) FROM {MARKET_TABLE} WHERE symbol=%s),
                           %s
                    ON CONFLICT (symbol) DO UPDATE SET
                        last_update=EXCLUDED.last_update, row_count=EXCLUDED.row_count,
                        start_date=EXCLUDED.start_date, end_date=EXCLUDED.end_date,
                        source=COALESCE(EXCLUDED.source, {META_TABLE}.source)
                    """,
                    (symbol, datetime.now(timezone.utc), symbol, symbol, symbol, source),
                )
            conn.commit()
        return max(written, 0)

    def load_data(
        self,
        symbol: str | list[str],
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """读行情，返回按 (symbol, date) 排好序的 DataFrame。"""
        symbols = [symbol] if isinstance(symbol, str) else list(symbol)
        clauses = ["symbol = ANY(%s)"]
        params: list = [symbols]
        if start_date:
            clauses.append("date >= %s")
            params.append(pd.to_datetime(start_date).date())
        if end_date:
            clauses.append("date <= %s")
            params.append(pd.to_datetime(end_date).date())

        sql = (
            f"SELECT symbol,date,open,high,low,close,volume FROM {MARKET_TABLE} "
            f"WHERE {' AND '.join(clauses)} ORDER BY symbol,date"
        )
        with self.engine.connect() as conn:
            frame = pd.read_sql_query(sql, conn, params=tuple(params))
        if not frame.empty:
            frame["date"] = pd.to_datetime(frame["date"])
        return frame

    def get_metadata(self, symbol: str | None = None) -> pd.DataFrame:
        """看看库里都有什么、更新到哪天了。"""
        sql = f"SELECT symbol,last_update,row_count,start_date,end_date,source FROM {META_TABLE}"
        params: list = []
        if symbol:
            sql += " WHERE symbol = %s"
            params.append(symbol)
        sql += " ORDER BY symbol"
        with self.engine.connect() as conn:
            return pd.read_sql_query(sql, conn, params=tuple(params) or None)

    def has_data(self, symbol: str, min_rows: int = 100) -> bool:
        """够不够用来建模——不够就该去下载。"""
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {MARKET_TABLE} WHERE symbol=%s", (symbol,))
            return cur.fetchone()[0] >= min_rows

    def latest_date(self, symbol: str):
        """该标的最新一根日线是哪天，用来做增量下载的起点。"""
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT MAX(date) FROM {MARKET_TABLE} WHERE symbol=%s", (symbol,))
            return cur.fetchone()[0]

    def list_symbols(self) -> list[str]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT DISTINCT symbol FROM {MARKET_TABLE} ORDER BY symbol")
            return [r[0] for r in cur.fetchall()]

    def delete_symbol(self, symbol: str) -> int:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(f"DELETE FROM {MARKET_TABLE} WHERE symbol=%s", (symbol,))
            deleted = cur.rowcount
            cur.execute(f"DELETE FROM {META_TABLE} WHERE symbol=%s", (symbol,))
            conn.commit()
        return deleted


if __name__ == "__main__":
    store = MarketDataStore()
    print(f"DSN: {store.dsn.split('@')[-1]}")
    meta = store.get_metadata()
    if meta.empty:
        print("库里还没有行情数据")
    else:
        print(meta.to_string(index=False))
