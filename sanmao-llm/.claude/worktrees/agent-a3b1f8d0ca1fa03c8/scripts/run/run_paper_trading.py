from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from quant_llm.config import load_config
from quant_llm.market_rules import market_rules_from_name
from quant_llm.paper_trading import build_latest_signals, load_latest_model, run_paper_account_update
from quant_llm.paths import resolve_model_dir, validate_artifact_isolation


def main() -> int:
    """第一版 paper trading 入口。

    它不接券商，不下真实订单，只做三件事：
      1. 读取 data/<strategy_id>/features/training_features.parquet 的最新特征。
      2. 加载 models/<strategy_id>/latest_model.joblib 生成最新 prob_up/long/flat。
      3. 写入 reports/<strategy_id>/paper_trading/ 下的模拟订单和模拟持仓。

    注意：
      运行它之前，应该先运行 scripts/run/run_all.sh。
      因为 run_all.sh 负责拉行情、抽取 Qwen 事件、生成 training_features，并让候选模型晋级 latest_model。
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/sec_filings_qwen.yaml")
    args = parser.parse_args()

    config = load_config(args.config)
    data_dir = Path(config["data_dir"])
    report_dir = Path(config["report_dir"])
    # 这里必须使用和 run_baseline.py 相同的路径解析逻辑。
    # 否则训练保存到 A 策略目录，模拟盘却从共享 models/ 目录加载旧模型，会非常危险。
    model_dir = resolve_model_dir(config, data_dir, args.config)
    validate_artifact_isolation(
        config,
        data_dir=data_dir,
        report_dir=report_dir,
        model_dir=model_dir,
        config_path=args.config,
    )
    paper_config = config.get("paper_trading", {})

    training_features_path = data_dir / "features" / "training_features.parquet"
    if not training_features_path.exists():
        raise SystemExit(f"Missing {training_features_path}. Run scripts/run/run_all.sh first.")

    model, metadata = load_latest_model(model_dir)
    feature_columns = metadata["feature_columns"]
    threshold = float(metadata.get("probability_threshold", config["probability_threshold"]))

    training_features = pd.read_parquet(training_features_path)
    signals = build_latest_signals(training_features, model, feature_columns, threshold)

    output_dir = Path(paper_config.get("output_dir", report_dir / "paper_trading"))
    output_dir.mkdir(parents=True, exist_ok=True)
    signals_path = output_dir / "paper_signals.csv"
    signals.to_csv(signals_path, index=False)

    summary = run_paper_account_update(
        signals,
        output_dir=output_dir,
        starting_cash=float(paper_config.get("starting_cash", 100_000.0)),
        max_symbol_weight=float(paper_config.get("max_symbol_weight", 0.25)),
        transaction_cost_bps=float(paper_config.get("transaction_cost_bps", config.get("transaction_cost_bps", 5))),
        market_rules=market_rules_from_name(paper_config.get("market", "US")),
    )

    print("== Paper Trading Signals ==")
    print(signals.to_string(index=False))
    print()
    print("== Paper Trading Summary ==")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
