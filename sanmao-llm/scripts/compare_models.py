"""对比单模型 vs Ensemble 性能"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd
from quant_llm.us_tech_loader import load_us_tech_stocks
from quant_llm.multi_stock_selector import MultiStockConfig, backtest_multi_stock


def prepare_features(df):
    features_dict = {}
    for symbol in df["symbol"].unique():
        symbol_data = df[df["symbol"] == symbol].copy().sort_values("date").reset_index(drop=True)
        symbol_data["daily_return"] = symbol_data["close"].pct_change()
        symbol_data["return_5d"] = symbol_data["close"].pct_change(5)
        symbol_data["return_10d"] = symbol_data["close"].pct_change(10)
        symbol_data["return_20d"] = symbol_data["close"].pct_change(20)
        symbol_data["volatility_10d"] = symbol_data["daily_return"].rolling(10).std()
        symbol_data["volume_ratio"] = symbol_data["volume"] / symbol_data["volume"].rolling(20).mean()
        gains = symbol_data["daily_return"].clip(lower=0)
        losses = -symbol_data["daily_return"].clip(upper=0)
        rs = gains.rolling(14).mean() / (losses.rolling(14).mean() + 1e-10)
        symbol_data["rsi_14"] = 100 - (100 / (1 + rs))
        symbol_data["ma_20"] = symbol_data["close"].rolling(20).mean()
        symbol_data["ma_ratio"] = symbol_data["close"] / symbol_data["ma_20"]
        symbol_data["target_up"] = (symbol_data["daily_return"].shift(-1) > 0).astype(int)
        features_dict[symbol] = symbol_data.dropna()
    return features_dict


def calc_metrics(results):
    results["cumulative"] = (1 + results["portfolio_return"]).cumprod()
    total_ret = results["cumulative"].iloc[-1] - 1
    daily = results["portfolio_return"]
    sharpe = daily.mean() / (daily.std() + 1e-10) * (252 ** 0.5)
    running_max = results["cumulative"].cummax()
    dd = (results["cumulative"] - running_max) / running_max
    max_dd = dd.min()
    win = (daily > 0).mean()
    return total_ret, sharpe, max_dd, win


print("Loading data...")
df = load_us_tech_stocks(start_date="2021-01-01")
features = prepare_features(df)

feature_cols = ["return_5d", "return_10d", "return_20d", "volatility_10d", "volume_ratio", "rsi_14", "ma_ratio"]
model_cfg = {"n_models": 5, "feature_fraction": 0.8, "n_estimators": 100, "num_leaves": 31, "learning_rate": 0.1}

# 单模型
print("\n" + "="*60)
print("Running Single LightGBM...")
print("="*60)
cfg1 = MultiStockConfig(symbols=["NVDA", "TSLA", "AMD", "MSFT", "GOOGL", "META"], top_k=3, use_ensemble=False, equal_weight=True)
r1 = backtest_multi_stock(features, cfg1, model_cfg, feature_cols, "2023-12-31")
m1 = calc_metrics(r1)

# Ensemble
print("\n" + "="*60)
print("Running Ensemble (5 models)...")
print("="*60)
cfg2 = MultiStockConfig(symbols=["NVDA", "TSLA", "AMD", "MSFT", "GOOGL", "META"], top_k=3, use_ensemble=True, equal_weight=True)
r2 = backtest_multi_stock(features, cfg2, model_cfg, feature_cols, "2023-12-31")
m2 = calc_metrics(r2)

# 结果
print("\n" + "="*60)
print("COMPARISON RESULTS")
print("="*60)
comp = pd.DataFrame([
    {"Model": "Single LightGBM", "Total Return": f"{m1[0]:.2%}", "Sharpe": f"{m1[1]:.2f}", "Max DD": f"{m1[2]:.2%}", "Win Rate": f"{m1[3]:.2%}"},
    {"Model": "Ensemble (5 models)", "Total Return": f"{m2[0]:.2%}", "Sharpe": f"{m2[1]:.2f}", "Max DD": f"{m2[2]:.2%}", "Win Rate": f"{m2[3]:.2%}"},
])
print("\n" + comp.to_string(index=False))

imp_ret = (m2[0] - m1[0]) / abs(m1[0])
imp_sharpe = (m2[1] - m1[1]) / abs(m1[1])
imp_dd = (m2[2] - m1[2]) / abs(m1[2])

print("\n" + "="*60)
print("IMPROVEMENT")
print("="*60)
print(f"Return: {imp_ret:+.2%}")
print(f"Sharpe: {imp_sharpe:+.2%}")
print(f"Drawdown: {imp_dd:+.2%} (negative = better)")

comp.to_csv("data/model_comparison.csv", index=False)
r1.to_csv("data/single_model_results.csv", index=False)
r2.to_csv("data/ensemble_model_results.csv", index=False)
print("\nSaved to data/")
