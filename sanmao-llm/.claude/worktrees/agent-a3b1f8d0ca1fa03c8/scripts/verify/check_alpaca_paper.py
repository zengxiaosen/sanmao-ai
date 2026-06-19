from __future__ import annotations

import json
import argparse
from pathlib import Path

import pandas as pd

from quant_llm.broker import AlpacaConfig, AlpacaTradingClient, reconcile_paper_portfolio_with_alpaca
from quant_llm.config import load_config, load_project_env


def main() -> int:
    """查看 Alpaca paper account 的账户、订单、持仓状态。"""
    parser = argparse.ArgumentParser(description="Check Alpaca paper account and reconcile with one strategy output.")
    parser.add_argument("--config", default="config/sec_filings_qwen.yaml")
    args = parser.parse_args()

    load_project_env()
    config = load_config(args.config)
    client = AlpacaTradingClient(AlpacaConfig.from_env())

    account = client.get_account()
    orders = client.get_orders(status="all", limit=10)
    positions = client.get_positions()

    print("== Alpaca Paper Account ==")
    print(
        json.dumps(
            {
                "status": account.get("status"),
                "currency": account.get("currency"),
                "buying_power": account.get("buying_power"),
                "cash": account.get("cash"),
                "portfolio_value": account.get("portfolio_value"),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    print()

    print("== Recent Orders ==")
    for order in orders:
        print(
            json.dumps(
                {
                    "id": order.get("id"),
                    "symbol": order.get("symbol"),
                    "side": order.get("side"),
                    "qty": order.get("qty"),
                    "type": order.get("type"),
                    "status": order.get("status"),
                    "submitted_at": order.get("submitted_at"),
                    "filled_at": order.get("filled_at"),
                    "filled_qty": order.get("filled_qty"),
                },
                ensure_ascii=False,
            )
        )
    print()

    print("== Positions ==")
    if not positions:
        print("No positions.")
    for position in positions:
        print(
            json.dumps(
                {
                    "symbol": position.get("symbol"),
                    "qty": position.get("qty"),
                    "market_value": position.get("market_value"),
                    "unrealized_pl": position.get("unrealized_pl"),
                },
                ensure_ascii=False,
            )
        )
    print()

    paper_portfolio_path = (
        Path(config.get("paper_trading", {}).get("output_dir", Path(config["report_dir"]) / "paper_trading"))
        / "paper_portfolio.csv"
    )
    if paper_portfolio_path.exists():
        paper_portfolio = pd.read_csv(paper_portfolio_path)
        reconciliation = reconcile_paper_portfolio_with_alpaca(paper_portfolio, positions)
        reconciliation_path = paper_portfolio_path.parent / "broker_reconciliation.csv"
        reconciliation.to_csv(reconciliation_path, index=False)
        print("== Reconciliation ==")
        print(reconciliation.to_string(index=False))
        print(f"Saved: {reconciliation_path}")
    else:
        print(f"Missing local paper portfolio: {paper_portfolio_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
