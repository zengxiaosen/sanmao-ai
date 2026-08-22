"""宏观因子模块

通过 yfinance 获取常用宏观指标：
- VIX：恐慌指数（市场波动率）
- DXY：美元指数
- ^TNX：10年期美债收益率
- GLD：黄金 ETF
- USO：原油 ETF

用途：作为市场环境特征，辅助选股
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf


MACRO_SYMBOLS = {
    "^VIX": "vix",          # 恐慌指数
    "DX-Y.NYB": "dxy",      # 美元指数
    "^TNX": "tnx",          # 10年期美债收益率
    "GLD": "gold",          # 黄金ETF
    "USO": "oil",           # 原油ETF
}


def fetch_macro_data(
    start_date: str = "2021-01-01",
    proxy: str | None = None,
) -> pd.DataFrame:
    """下载宏观数据
    
    Args:
        start_date: 开始日期
        proxy: HTTP 代理
        
    Returns:
        DataFrame with columns [date, vix, dxy, tnx, gold, oil]
    """
    if proxy:
        os.environ["HTTP_PROXY"] = proxy
        os.environ["HTTPS_PROXY"] = proxy
    
    all_data = {}
    
    for symbol, name in MACRO_SYMBOLS.items():
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, auto_adjust=True)
            
            if df.empty:
                print(f"Warning: No data for {symbol} ({name})")
                continue
            
            # 只保留收盘价
            df = df[["Close"]].rename(columns={"Close": name})
            all_data[name] = df
            
            print(f"Downloaded {symbol} ({name}): {len(df)} rows")
            
        except Exception as e:
            print(f"Error downloading {symbol}: {e}")
            continue
    
    if not all_data:
        raise ValueError("No macro data downloaded")
    
    # 合并所有指标（按日期对齐）
    result = pd.concat(all_data.values(), axis=1, join="outer")
    result = result.reset_index().rename(columns={"Date": "date"})
    result["date"] = pd.to_datetime(result["date"]).dt.strftime("%Y-%m-%d")
    
    # 前向填充缺失值（宏观指标周末不更新，用最近值）
    result = result.fillna(method="ffill")
    
    return result


def add_macro_features(
    stock_df: pd.DataFrame,
    macro_df: pd.DataFrame,
) -> pd.DataFrame:
    """将宏观因子合并到股票数据
    
    Args:
        stock_df: 股票数据，包含 date 列
        macro_df: 宏观数据，包含 date 列
        
    Returns:
        合并后的 DataFrame，新增宏观因子列
    """
    # 按日期左连接
    merged = stock_df.merge(macro_df, on="date", how="left")
    
    # 前向填充缺失值（股票交易日可能多于宏观数据更新日）
    macro_cols = ["vix", "dxy", "tnx", "gold", "oil"]
    for col in macro_cols:
        if col in merged.columns:
            merged[col] = merged[col].fillna(method="ffill")
    
    # 计算宏观因子的变化率
    for col in macro_cols:
        if col in merged.columns:
            merged[f"{col}_change_5d"] = merged[col].pct_change(5)
            merged[f"{col}_change_20d"] = merged[col].pct_change(20)
    
    return merged


if __name__ == "__main__":
    # 测试：下载并保存宏观数据
    print("Downloading macro data...")
    
    # 如果需要代理，取消下面的注释
    # proxy = "http://127.0.0.1:7890"
    proxy = None
    
    macro_df = fetch_macro_data(proxy=proxy)
    
    print(f"\nDownloaded {len(macro_df)} rows")
    print(f"Date range: {macro_df[date].min()} to {macro_df[date].max()}")
    print(f"\nColumns: {macro_df.columns.tolist()}")
    print(f"\nSample data:")
    print(macro_df.tail(10))
    
    # 保存到 CSV
    macro_df.to_csv("data/macro_factors.csv", index=False)
    print(f"\nSaved to data/macro_factors.csv")
