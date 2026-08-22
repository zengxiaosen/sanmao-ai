"""美股科技板块数据加载（支持数据库缓存）

优先从 SQLite 数据库读取，数据不存在或过期时通过代理下载更新。
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

from quant_llm.data_store import MarketDataStore


US_TECH_SYMBOLS = ["NVDA", "TSLA", "AMD", "MSFT", "GOOGL", "META"]


def fetch_from_yfinance(
    symbols: list[str],
    start_date: str = "2021-01-01",
    proxy: str | None = None,
) -> pd.DataFrame:
    """从 yfinance 下载数据
    
    Args:
        symbols: 股票代码列表
        start_date: 开始日期
        proxy: HTTP 代理地址（如 http://127.0.0.1:7890）
    """
    if proxy:
        os.environ["HTTP_PROXY"] = proxy
        os.environ["HTTPS_PROXY"] = proxy
    
    all_data = []
    
    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, auto_adjust=True)
            
            if df.empty:
                print(f"Warning: No data for {symbol}")
                continue
            
            df = df.reset_index()
            df["symbol"] = symbol
            df = df.rename(columns={
                "Date": "date",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            })
            df = df[["symbol", "date", "open", "high", "low", "close", "volume"]]
            df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
            
            all_data.append(df)
            print(f"Downloaded {symbol}: {len(df)} rows")
            
        except Exception as e:
            print(f"Error downloading {symbol}: {e}")
            continue
    
    if not all_data:
        raise ValueError("No data downloaded")
    
    return pd.concat(all_data, ignore_index=True)


def load_us_tech_stocks(
    symbols: list[str] | None = None,
    start_date: str = "2021-01-01",
    end_date: str | None = None,
    force_update: bool = False,
    proxy: str | None = None,
    db_path: str = "data/market_data.db",
) -> pd.DataFrame:
    """加载美股科技板块数据（优先从数据库读取）
    
    Args:
        symbols: 股票代码列表，None=使用默认科技股池
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD，None=今天
        force_update: 强制重新下载
        proxy: HTTP 代理地址
        db_path: 数据库路径
        
    Returns:
        DataFrame with columns [symbol, date, open, high, low, close, volume]
    """
    if symbols is None:
        symbols = US_TECH_SYMBOLS
    
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")
    
    store = MarketDataStore(db_path)
    
    # 检查数据库中已有的数据
    if not force_update:
        metadata = store.get_metadata()
        existing_symbols = set(metadata["symbol"].tolist())
        missing_symbols = [s for s in symbols if s not in existing_symbols]
        
        # 检查是否需要增量更新（数据过期）
        stale_symbols = []
        for _, row in metadata.iterrows():
            if row["symbol"] in symbols:
                last_update = datetime.fromisoformat(row["last_update"])
                if datetime.now() - last_update > timedelta(days=1):
                    stale_symbols.append(row["symbol"])
        
        need_update = missing_symbols + stale_symbols
        
        if need_update:
            print(f"Updating data for: {need_update}")
            try:
                new_data = fetch_from_yfinance(need_update, start_date, proxy)
                store.save_data(new_data)
                print(f"Updated {len(new_data)} rows")
            except Exception as e:
                print(f"Update failed: {e}, using cached data")
    else:
        # 强制更新：重新下载所有数据
        print(f"Force updating all symbols: {symbols}")
        new_data = fetch_from_yfinance(symbols, start_date, proxy)
        for symbol in symbols:
            store.delete_symbol(symbol)
        store.save_data(new_data)
    
    # 从数据库加载
    df = store.load_data(symbols, start_date, end_date)
    
    if df.empty:
        raise ValueError(f"No data found for {symbols}")
    
    return df


def get_latest_prices(
    symbols: list[str] | None = None,
    proxy: str | None = None,
) -> pd.DataFrame:
    """获取最新价格（实时查询，不缓存）"""
    if symbols is None:
        symbols = US_TECH_SYMBOLS
    
    if proxy:
        os.environ["HTTP_PROXY"] = proxy
        os.environ["HTTPS_PROXY"] = proxy
    
    results = []
    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            results.append({
                "symbol": symbol,
                "price": info.get("currentPrice", 0.0),
                "change_pct": info.get("regularMarketChangePercent", 0.0),
                "volume": info.get("volume", 0),
            })
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
    
    return pd.DataFrame(results)


if __name__ == "__main__":
    # 测试：从数据库加载数据
    print("Loading from database...")
    df = load_us_tech_stocks(start_date="2024-01-01")
    print(f"\nLoaded {len(df)} rows for {df['symbol'].nunique()} symbols")
    print(df.groupby("symbol").size())
