from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from quant_llm.config import load_config


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def main() -> int:
    """用最直观的方式打印最近一次回测结果。

    这个脚本只读报告文件，不重新训练模型。

    默认读取 config/sec_filings_qwen.yaml 里定义的 report_dir。

    用途：
        你想快速看“这次有没有赚钱、最大回撤多少、最新信号是什么”，直接运行：
            .venv/bin/python scripts/verify/show_report.py --config config/sec_filings_qwen.yaml
    """
    parser = argparse.ArgumentParser(description="Print a human-readable backtest report for one strategy config.")
    parser.add_argument("--config", default="config/sec_filings_qwen.yaml")
    args = parser.parse_args()

    config = load_config(args.config)
    report_dir = Path(config["report_dir"])
    metrics_path = report_dir / "metrics.json"
    backtest_daily_path = report_dir / "backtest_daily.csv"
    latest_signals_path = report_dir / "latest_signals.csv"

    if not metrics_path.exists():
        raise SystemExit(f"Missing {metrics_path}. Run scripts/run/run_all.sh first, or pass the correct --config.")

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    backtest = metrics["backtest"]

    print("== Backtest Summary ==")
    print(f"Config:            {args.config}")
    print(f"Market:            {metrics.get('market', config.get('market', 'UNKNOWN'))}")
    print(f"Strategy:          {metrics.get('strategy_id', config.get('strategy_id', 'UNKNOWN'))}")
    print(f"Total return:      {pct(backtest['total_return'])}")
    print(f"Annual return:     {pct(backtest['annual_return'])}")
    print(f"Annual volatility: {pct(backtest['annual_volatility'])}")
    print(f"Sharpe:            {backtest['sharpe']:.3f}")
    print(f"Max drawdown:      {pct(backtest['max_drawdown'])}")
    print(f"Exposure:          {pct(backtest['exposure'])}")
    print()

    artifacts = metrics.get("artifacts", {})
    if artifacts:
        print("== Key Artifacts ==")
        for name in [
            "candidate_model",
            "candidate_model_metadata",
            "latest_model",
            "latest_model_metadata",
            "training_features",
            "predictions",
            "backtest_daily_csv",
            "latest_signals",
        ]:
            if name in artifacts:
                print(f"{name}: {artifacts[name]}")
        print()

    if backtest_daily_path.exists():
        daily = pd.read_csv(backtest_daily_path)
        print("== Equity Curve Tail ==")
        print(daily.tail(5).to_string(index=False))
        print()

    if latest_signals_path.exists():
        signals = pd.read_csv(latest_signals_path)
        print("== Latest Signals ==")
        print(signals.to_string(index=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
