"""对比单模型 vs Ensemble 性能"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd
from quant_llm.us_tech_loader import load_us_tech_stocks
from quant_llm.multi_stock_selector import MultiStockConfig, backtest_multi_stock


def prepare_features(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """准备特征"""
    features_dict = {}
    
    for symbol in df["symbol"].unique():
        symbol_data = df[df["symbol"] == symbol].copy()
        symbol_data = symbol_data.sort_values("date").reset_index(drop=True)
        
        # 技术因子
        symbol_data["daily_return"] = symbol_data["close"].pct_change()
        symbol_data["return_5d"] = symbol_data["close"].pct_change(5)
        symbol_data["return_10d"] = symbol_data["close"].pct_change(10)
        symbol_data["return_20d"] = symbol_data["close"].pct_change(20)
        symbol_data["volatility_10d"] = symbol_data["daily_return"].rolling(10).std()
        symbol_data["volatility_20d"] = symbol_data["daily_return"].rolling(20).std()
        symbol_data["volume_ratio"] = symbol_data["volume"] / symbol_data["volume"].rolling(20).mean()
        
        gains = symbol_data["daily_return"].clip(lower=0)
        losses = -symbol_data["daily_return"].clip(upper=0)
        avg_gain = gains.rolling(14).mean()
        avg_loss = losses.rolling(14).mean()
        rs = avg_gain / (avg_loss + 1e-10)
        symbol_data["rsi_14"] = 100 - (100 / (1 + rs))
        
        symbol_data["ma_5"] = symbol_data["close"].rolling(5).mean()
        symbol_data["ma_20"] = symbol_data["close"].rolling(20).mean()
        symbol_data["ma_ratio"] = symbol_data["close"] / symbol_data["ma_20"]
        
        symbol_data["target_up"] = (symbol_data["daily_return"].shift(-1) > 0).astype(int)
        symbol_data = symbol_data.dropna()
        
        features_dict[symbol] = symbol_data
    
    return features_dict


def run_backtest(use_ensemble: bool, label: str):
    """运行单次回测"""
    print("
" + "="*60)
    print(f"Running: {label}")
    print("="*60)
    
    df = load_us_tech_stocks(start_date="2021-01-01")
    features_dict = prepare_features(df)
    
    feature_columns = [
        "return_5d", "return_10d", "return_20d",
        "volatility_10d", "volatility_20d",
        "volume_ratio", "rsi_14", "ma_ratio",
    ]
    
    config = MultiStockConfig(
        symbols=["NVDA", "TSLA", "AMD", "MSFT", "GOOGL", "META"],
        top_k=3,
        use_ensemble=use_ensemble,
        equal_weight=True,
    )
    
    model_config = {
        "n_models": 5,
        "feature_fraction": 0.8,
        "n_estimators": 100,
        "num_leaves": 31,
        "learning_rate": 0.1,
    }
    
    results = backtest_multi_stock(
        features_dict=features_dict,
        config=config,
        model_config=model_config,
        feature_columns=feature_columns,
        train_end_date="2023-12-31",
    )
    
    # 计算指标
    results["cumulative_return"] = (1 + results["portfolio_return"]).cumprod()
    total_return = results["cumulative_return"].iloc[-1] - 1
    daily_returns = results["portfolio_return"]
    sharpe = daily_returns.mean() / (daily_returns.std() + 1e-10) * (252 ** 0.5)
    
    cumulative = results["cumulative_return"]
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max
    max_drawdown = drawdown.min()
    
    win_rate = (daily_returns > 0).mean()
    
    return {
        "label": label,
        "total_return": total_return,
        "sharpe_ratio": sharpe,
        "max_drawdown": max_drawdown,
        "win_rate": win_rate,
        "results_df": results,
    }


if __name__ == "__main__":
    # 运行两个版本
    single_result = run_backtest(use_ensemble=False, label="Single LightGBM")
    ensemble_result = run_backtest(use_ensemble=True, label="Ensemble (5 models)")
    
    # 对比结果
    print("
" + "="*60)
    print("COMPARISON RESULTS")
    print("="*60)
    
    comparison = pd.DataFrame([
        {
            "Model": single_result["label"],
            "Total Return": f"{single_result[total_return]:.2%}",
            "Sharpe Ratio": f"{single_result[sharpe_ratio]:.2f}",
            "Max Drawdown": f"{single_result[max_drawdown]:.2%}",
            "Win Rate": f"{single_result[win_rate]:.2%}",
        },
        {
            "Model": ensemble_result["label"],
            "Total Return": f"{ensemble_result[total_return]:.2%}",
            "Sharpe Ratio": f"{ensemble_result[sharpe_ratio]:.2f}",
            "Max Drawdown": f"{ensemble_result[max_drawdown]:.2%}",
            "Win Rate": f"{ensemble_result[win_rate]:.2%}",
        },
    ])
    
    print("\n" + comparison.to_string(index=False))
    
    # 计算改善幅度
    print("
" + "="*60)
    print("IMPROVEMENT")
    print("="*60)
    
    return_improvement = (ensemble_result["total_return"] - single_result["total_return"]) / abs(single_result["total_return"])
    sharpe_improvement = (ensemble_result["sharpe_ratio"] - single_result["sharpe_ratio"]) / abs(single_result["sharpe_ratio"])
    drawdown_improvement = (ensemble_result["max_drawdown"] - single_result["max_drawdown"]) / abs(single_result["max_drawdown"])
    
    print(f"Return improvement: {return_improvement:+.2%}")
    print(f"Sharpe improvement: {sharpe_improvement:+.2%}")
    print(f"Drawdown reduction: {drawdown_improvement:+.2%} (negative = better)")
    
    # 保存结果
    comparison.to_csv("data/model_comparison.csv", index=False)
    single_result["results_df"].to_csv("data/single_model_results.csv", index=False)
    ensemble_result["results_df"].to_csv("data/ensemble_model_results.csv", index=False)
    
    print(f"\nResults saved to data/")
