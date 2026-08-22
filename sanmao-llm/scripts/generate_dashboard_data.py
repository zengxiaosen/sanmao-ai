"""生成前端看板需要的数据"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd
import json
from datetime import datetime


def load_backtest_results():
    """加载回测结果"""
    single = pd.read_csv("data/single_model_results.csv")
    ensemble = pd.read_csv("data/ensemble_model_results.csv")
    return single, ensemble


def calculate_metrics(df):
    """计算各项指标"""
    df["cumulative"] = (1 + df["portfolio_return"]).cumprod()
    
    total_return = df["cumulative"].iloc[-1] - 1
    daily_returns = df["portfolio_return"]
    
    # 年化收益
    n_days = len(df)
    annualized_return = (1 + total_return) ** (252 / n_days) - 1
    
    # 夏普比率
    sharpe = daily_returns.mean() / (daily_returns.std() + 1e-10) * (252 ** 0.5)
    
    # 最大回撤
    running_max = df["cumulative"].cummax()
    drawdown = (df["cumulative"] - running_max) / running_max
    max_drawdown = drawdown.min()
    
    # 胜率
    win_rate = (daily_returns > 0).mean()
    
    # 月度收益
    df["year_month"] = pd.to_datetime(df["date"]).dt.to_period("M")
    monthly_returns = df.groupby("year_month")["portfolio_return"].apply(
        lambda x: (1 + x).prod() - 1
    )
    
    return {
        "total_return": total_return,
        "annualized_return": annualized_return,
        "sharpe_ratio": sharpe,
        "max_drawdown": max_drawdown,
        "win_rate": win_rate,
        "monthly_returns": monthly_returns.to_dict(),
        "cumulative_curve": df[["date", "cumulative"]].to_dict("records"),
        "drawdown_curve": df[["date"]].assign(drawdown=drawdown).to_dict("records"),
    }


def generate_comparison_json():
    """生成对比数据 JSON"""
    single, ensemble = load_backtest_results()
    
    single_metrics = calculate_metrics(single)
    ensemble_metrics = calculate_metrics(ensemble)
    
    # 构建前端需要的数据结构
    output = {
        "generated_at": datetime.now().isoformat(),
        "models": {
            "single": {
                "name": "单模型 LightGBM",
                "description": "使用单个 LightGBM 模型",
                "metrics": {
                    "total_return": round(single_metrics["total_return"] * 100, 2),
                    "annualized_return": round(single_metrics["annualized_return"] * 100, 2),
                    "sharpe_ratio": round(single_metrics["sharpe_ratio"], 2),
                    "max_drawdown": round(single_metrics["max_drawdown"] * 100, 2),
                    "win_rate": round(single_metrics["win_rate"] * 100, 2),
                },
                "cumulative_curve": single_metrics["cumulative_curve"],
                "drawdown_curve": single_metrics["drawdown_curve"],
            },
            "ensemble": {
                "name": "集成模型（5 个 LightGBM）",
                "description": "使用 5 个不同随机种子的 LightGBM 集成，预测取中位数",
                "metrics": {
                    "total_return": round(ensemble_metrics["total_return"] * 100, 2),
                    "annualized_return": round(ensemble_metrics["annualized_return"] * 100, 2),
                    "sharpe_ratio": round(ensemble_metrics["sharpe_ratio"], 2),
                    "max_drawdown": round(ensemble_metrics["max_drawdown"] * 100, 2),
                    "win_rate": round(ensemble_metrics["win_rate"] * 100, 2),
                },
                "cumulative_curve": ensemble_metrics["cumulative_curve"],
                "drawdown_curve": ensemble_metrics["drawdown_curve"],
            },
        },
        "comparison": {
            "return_diff": round((ensemble_metrics["total_return"] - single_metrics["total_return"]) * 100, 2),
            "sharpe_diff": round(ensemble_metrics["sharpe_ratio"] - single_metrics["sharpe_ratio"], 2),
            "drawdown_diff": round((ensemble_metrics["max_drawdown"] - single_metrics["max_drawdown"]) * 100, 2),
        },
        "stock_pool": ["NVDA", "TSLA", "AMD", "MSFT", "GOOGL", "META"],
        "strategy": {
            "train_period": "2021-01-01 至 2023-12-31",
            "test_period": "2024-01-01 至今",
            "top_k": 3,
            "rebalance": "每日",
            "weight": "等权",
        },
    }
    
    # 保存到前端 assets 目录
    frontend_path = Path("/opt/sanmao/quant-dashboard/assets/backtest_comparison.json")
    frontend_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(frontend_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"✓ Generated: {frontend_path}")
    print(f"  Single model return: {single_metrics['total_return']:.2%}")
    print(f"  Ensemble return: {ensemble_metrics['total_return']:.2%}")
    print(f"  Difference: {(ensemble_metrics['total_return'] - single_metrics['total_return']):.2%}")


if __name__ == "__main__":
    generate_comparison_json()
