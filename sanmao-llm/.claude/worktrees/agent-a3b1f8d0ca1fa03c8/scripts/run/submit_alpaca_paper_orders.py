from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from quant_llm.broker import (
    AlpacaConfig,
    AlpacaTradingClient,
    build_broker_order_plan,
    check_order_risk_limits,
    load_latest_paper_orders,
    submit_order_plan_to_alpaca,
)
from quant_llm.config import load_config, load_project_env


def _latest_run_id(order_plan) -> str:
    """取本次准备提交的 run_id。

    paper_orders.csv 每次模拟盘运行都会生成一个 run_id。
    券商提交也必须以 run_id 为幂等键：同一个 run_id 不能重复提交。
    """
    run_ids = order_plan["run_id"].dropna().unique()
    if len(run_ids) != 1:
        raise ValueError(f"Expected exactly one run_id in latest order plan, got {run_ids}")
    return str(run_ids[0])


def _already_submitted(result_path: Path, run_id: str) -> bool:
    """检查某个 run_id 是否已经提交过券商 paper orders。"""
    if not result_path.exists():
        return False
    history = pd.read_csv(result_path)
    if history.empty or "run_id" not in history.columns or "submitted" not in history.columns:
        return False
    same_run = history.loc[history["run_id"] == run_id]
    if same_run.empty:
        return False
    return bool(same_run["submitted"].astype(bool).any())


def main() -> int:
    """把本地模拟盘订单转换为 Alpaca paper orders。

    默认不会提交订单，只生成 broker_order_preview.csv。
    要真的提交到 Alpaca paper account，需要同时满足：
      1. config 里 broker.submit_orders: true
      2. .env 里有 ALPACA_API_KEY_ID / ALPACA_API_SECRET_KEY

    注意：
      这个脚本只接 Alpaca paper API。
      不支持真实账户，除非以后单独做 live-trading 安全审查。
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/sec_filings_qwen.yaml")
    parser.add_argument(
        "--submit-orders",
        action="store_true",
        help="Submit to Alpaca paper API. Without this flag the script only writes broker_order_preview.csv.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow re-submitting an already submitted run_id. Use only for manual recovery.",
    )
    args = parser.parse_args()

    load_project_env()
    config = load_config(args.config)
    report_dir = Path(config["report_dir"])
    broker_config = config.get("broker", {})
    paper_output_dir = Path(config.get("paper_trading", {}).get("output_dir", report_dir / "paper_trading"))
    paper_orders_path = paper_output_dir / "paper_orders.csv"

    order_plan = build_broker_order_plan(
        load_latest_paper_orders(paper_orders_path),
        min_notional=float(broker_config.get("min_notional", 10.0)),
    )

    preview_path = paper_output_dir / "broker_order_preview.csv"
    order_plan.to_csv(preview_path, index=False)
    print(f"Broker order preview: {preview_path}")
    print(order_plan.to_string(index=False))

    should_submit = bool(broker_config.get("submit_orders", False)) or args.submit_orders
    if not should_submit:
        print("submit_orders is false and --submit-orders was not passed; not submitting to Alpaca paper API.")
        return 0

    result_path = paper_output_dir / "broker_order_results.csv"
    run_id = _latest_run_id(order_plan)
    if _already_submitted(result_path, run_id) and not args.force:
        raise SystemExit(
            f"Run {run_id} already has submitted broker orders in {result_path}. "
            "Refusing duplicate submission. Use --force only for manual recovery."
        )

    alpaca_config = AlpacaConfig.from_env(
        base_url=broker_config.get("base_url"),
        allow_live_trading=bool(broker_config.get("allow_live_trading", False)),
    )
    client = AlpacaTradingClient(alpaca_config)
    account = client.get_account()
    print(f"Alpaca paper account status: {account.get('status')}, buying_power={account.get('buying_power')}")
    open_orders = client.get_orders(status="open", limit=50)

    risk_passed, risk_reasons = check_order_risk_limits(order_plan, account, open_orders, broker_config.get("risk_limits"))
    print("== Broker Risk Checks ==")
    for reason in risk_reasons:
        print(reason)
    if not risk_passed:
        raise SystemExit("Broker risk checks failed; refusing to submit orders.")

    result = submit_order_plan_to_alpaca(
        order_plan,
        client=client,
        time_in_force=str(broker_config.get("time_in_force", "day")),
    )
    if result_path.exists():
        result.to_csv(result_path, mode="a", header=False, index=False)
    else:
        result.to_csv(result_path, index=False)
    print(f"Broker order results: {result_path}")
    print(result.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
