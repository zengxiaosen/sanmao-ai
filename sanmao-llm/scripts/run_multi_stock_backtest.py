"""多股票选股回测脚本

使用 LightGBM + Ensemble 对 6 支美股科技股进行选股回测
"""
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd
from quant_llm.us_tech_loader import load_us_tech_stocks
from quant_llm.multi_stock_selector import MultiStockConfig, backtest_multi_stock
# Removed unused import


def prepare_features(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """为每只股票准备特征
    
    Args:
        df: 原始市场数据
        
    Returns:
        {symbol: features_df} 每个 df 包含因子和 target_up
    """
    features_dict = {}
    
    for symbol in df["symbol"].unique():
        symbol_data = df[df["symbol"] == symbol].copy()
        symbol_data = symbol_data.sort_values("date").reset_index(drop=True)
        
        # 计算技术因子（简化版：只用价格动量）
        symbol_data["daily_return"] = symbol_data["close"].pct_change()
        symbol_data["return_5d"] = symbol_data["close"].pct_change(5)
        symbol_data["return_10d"] = symbol_data["close"].pct_change(10)
        symbol_data["return_20d"] = symbol_data["close"].pct_change(20)
        
        # 波动率
        symbol_data["volatility_10d"] = symbol_data["daily_return"].rolling(10).std()
        symbol_data["volatility_20d"] = symbol_data["daily_return"].rolling(20).std()
        
        # 成交量
        symbol_data["volume_ratio"] = symbol_data["volume"] / symbol_data["volume"].rolling(20).mean()
        
        # RSI（简化版）
        gains = symbol_data["daily_return"].clip(lower=0)
        losses = -symbol_data["daily_return"].clip(upper=0)
        avg_gain = gains.rolling(14).mean()
        avg_loss = losses.rolling(14).mean()
        rs = avg_gain / (avg_loss + 1e-10)
        symbol_data["rsi_14"] = 100 - (100 / (1 + rs))
        
        # 移动平均
        symbol_data["ma_5"] = symbol_data["close"].rolling(5).mean()
        symbol_data["ma_20"] = symbol_data["close"].rolling(20).mean()
        symbol_data["ma_ratio"] = symbol_data["close"] / symbol_data["ma_20"]
        
        # 标签：次日收益 > 0
        symbol_data["target_up"] = (symbol_data["daily_return"].shift(-1) > 0).astype(int)
        
        # 删除 NaN
        symbol_data = symbol_data.dropna()
        
        features_dict[symbol] = symbol_data
        print(f"{symbol}: {len(symbol_data)} samples prepared")
    
    return features_dict


if __name__ == "__main__":
    print("=" * 60)
    print("Multi-Stock Selection Backtest")
    print("=" * 60)
    
    # 1. 加载数据
    print("\n[1/4] Loading market data...")
    df = load_us_tech_stocks(start_date="2021-01-01")
    print(f"Loaded {len(df)} rows for {df['symbol'].nunique()} symbols")
    
    # 2. 准备特征
    print("\n[2/4] Preparing features...")
    features_dict = prepare_features(df)
    
    feature_columns = [
        "return_5d", "return_10d", "return_20d",
        "volatility_10d", "volatility_20d",
        "volume_ratio", "rsi_14", "ma_ratio",
    ]
    
    # 3. 配置选股策略
    config = MultiStockConfig(
        symbols=["NVDA", "TSLA", "AMD", "MSFT", "GOOGL", "META"],
        top_k=3,  # 选 top 3
        use_ensemble=True,  # 使用集成模型
        equal_weight=True,  # 等权配置
    )
    
    model_config = {
        "n_models": 5,  # 5 个模型集成
        "feature_fraction": 0.8,
        "n_estimators": 100,  # 减少树的数量加快训练
        "num_leaves": 31,
        "learning_rate": 0.1,
    }
    
    # 4. 回测
    print("\n[3/4] Running backtest...")
    print(f"Training period: 2021-01-01 to 2023-12-31")
    print(f"Testing period: 2024-01-01 onwards")
    
    results = backtest_multi_stock(
        features_dict=features_dict,
        config=config,
        model_config=model_config,
        feature_columns=feature_columns,
        train_end_date="2023-12-31",
    )
    
    # 5. 分析结果
    print("\n[4/4] Analyzing results...")
    print(f"\nBacktest summary:")
    print(f"Total trading days: {len(results)}")
    
    if len(results) > 0:
        # 计算累计收益
        results["cumulative_return"] = (1 + results["portfolio_return"]).cumprod()
        
        # 统计
        total_return = results["cumulative_return"].iloc[-1] - 1
        daily_returns = results["portfolio_return"]
        sharpe = daily_returns.mean() / (daily_returns.std() + 1e-10) * (252 ** 0.5)
        
        # 最大回撤
        cumulative = results["cumulative_return"]
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min()
        
        print(f"\nPerformance metrics:")
        print(f"  Total return: {total_return:.2%}")
        print(f"  Annualized return: {(1 + total_return) ** (252 / len(results)) - 1:.2%}")
        print(f"  Sharpe ratio: {sharpe:.2f}")
        print(f"  Max drawdown: {max_drawdown:.2%}")
        print(f"  Win rate: {(daily_returns > 0).mean():.2%}")
        
        # 保存结果
        results.to_csv("data/multi_stock_backtest_results.csv", index=False)
        print(f"\nResults saved to data/multi_stock_backtest_results.csv")
        
        # 显示最近的选股
        print("\nRecent portfolio selections:")
        print(results.tail(10)[["date", "selected_symbols", "portfolio_return"]])
    else:
        print("No backtest results generated")

