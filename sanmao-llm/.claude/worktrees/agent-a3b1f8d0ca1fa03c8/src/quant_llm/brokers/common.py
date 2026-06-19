from __future__ import annotations

from pathlib import Path

import pandas as pd

from quant_llm.brokers.alpaca import AlpacaTradingClient, alpaca_symbol


def load_latest_paper_orders(paper_orders_path: str | Path) -> pd.DataFrame:
    """读取本地模拟盘最新一轮订单。

    paper_orders.csv 是追加写入的，每次模拟盘运行都有一个 run_id。
    提交给券商 paper API 时，只应该提交最新 run_id，避免重复提交历史订单。
    """
    paper_orders_path = Path(paper_orders_path)
    if not paper_orders_path.exists():
        raise FileNotFoundError(f"Missing {paper_orders_path}. Run scripts/run/run_paper_trading.py first.")

    orders = pd.read_csv(paper_orders_path)
    if orders.empty:
        raise ValueError(f"No paper orders in {paper_orders_path}")

    latest_run_id = orders["run_id"].iloc[-1]
    latest = orders.loc[orders["run_id"] == latest_run_id].copy()
    return latest.reset_index(drop=True)


def build_broker_order_plan(
    paper_orders: pd.DataFrame,
    min_notional: float = 10.0,
) -> pd.DataFrame:
    """把本地模拟盘订单转换成 broker-neutral 订单计划。

    这个函数不连接券商、不提交订单，只生成“计划”。

    设计原因：
      1. 模拟盘会输出 buy/sell/hold。
      2. broker API 只应该收到真正需要执行的 buy/sell。
      3. 金额太小的调仓没有意义，还会增加费用和噪音，所以按 min_notional 跳过。
    """
    rows = []
    for order in paper_orders.itertuples(index=False):
        delta_shares = float(order.delta_shares)
        notional = float(order.notional)
        # hold、0 股、金额太小的订单都不提交到券商。
        # 它们仍然写入 preview，方便审计“为什么没下单”。
        if getattr(order, "action") == "hold" or abs(delta_shares) <= 0 or abs(notional) < float(min_notional):
            rows.append(
                {
                    "run_id": order.run_id,
                    "symbol": order.symbol,
                    "alpaca_symbol": alpaca_symbol(order.symbol),
                    "side": "hold",
                    "qty": 0.0,
                    "notional": notional,
                    "skip_reason": "hold_or_below_min_notional",
                }
            )
            continue

        rows.append(
            {
                "run_id": order.run_id,
                "symbol": order.symbol,
                "alpaca_symbol": alpaca_symbol(order.symbol),
                "side": "buy" if delta_shares > 0 else "sell",
                "qty": abs(delta_shares),
                "notional": abs(notional),
                "skip_reason": "",
            }
        )

    return pd.DataFrame(rows)


def submit_order_plan_to_alpaca(
    order_plan: pd.DataFrame,
    client: AlpacaTradingClient,
    time_in_force: str = "day",
) -> pd.DataFrame:
    """把订单计划提交到 Alpaca paper trading。

    注意：
      这里只负责执行已经通过风控的订单计划。
      风控和防重复在 scripts/run/submit_alpaca_paper_orders.py 中先完成。
    """
    results = []
    for order in order_plan.itertuples(index=False):
        if order.side == "hold":
            # hold 行不调用券商 API，只记录 skipped。
            results.append(
                {
                    "run_id": order.run_id,
                    "symbol": order.symbol,
                    "alpaca_symbol": order.alpaca_symbol,
                    "side": order.side,
                    "qty": order.qty,
                    "submitted": False,
                    "broker_order_id": "",
                    "status": "skipped",
                    "message": order.skip_reason,
                }
            )
            continue

        response = client.submit_market_order(
            symbol=order.alpaca_symbol,
            side=order.side,
            qty=float(order.qty),
            time_in_force=time_in_force,
        )
        results.append(
            {
                "run_id": order.run_id,
                "symbol": order.symbol,
                "alpaca_symbol": order.alpaca_symbol,
                "side": order.side,
                "qty": order.qty,
                "submitted": True,
                "broker_order_id": response.get("id", ""),
                "status": response.get("status", ""),
                "message": "",
            }
        )

    return pd.DataFrame(results)


def check_order_risk_limits(
    order_plan: pd.DataFrame,
    account: dict,
    open_orders: list[dict],
    risk_config: dict | None = None,
) -> tuple[bool, list[str]]:
    """券商提交前的最小风控检查。

    当前用于 paper trading，但这些检查也是未来实盘的底线：
      1. 账户必须 ACTIVE。
      2. 有未完成 open orders 时默认禁止继续提交，防止重复挂单。
      3. 单笔订单不能超过账户权益上限。
      4. 本次提交总金额不能超过账户权益上限。

    返回：
      passed:
        True 才允许提交。
      reasons:
        每条检查的 PASS/FAIL 文本，用于日志和人工审计。
    """
    risk_config = risk_config or {}
    max_order_notional_pct = float(risk_config.get("max_order_notional_pct", 0.30))
    max_total_notional_pct = float(risk_config.get("max_total_notional_pct", 0.50))
    block_if_open_orders = bool(risk_config.get("block_if_open_orders", True))

    equity = float(account.get("portfolio_value") or account.get("equity") or 0.0)
    active_orders = order_plan.loc[order_plan["side"].isin(["buy", "sell"])].copy()
    max_order_notional = float(active_orders["notional"].max()) if not active_orders.empty else 0.0
    total_notional = float(active_orders["notional"].sum()) if not active_orders.empty else 0.0

    checks: list[tuple[bool, str]] = []
    checks.append((account.get("status") == "ACTIVE", f"account.status={account.get('status')} must be ACTIVE"))
    checks.append((equity > 0, f"portfolio_value={equity:.2f} must be positive"))

    if equity > 0:
        checks.append(
            (
                max_order_notional <= equity * max_order_notional_pct,
                f"max_order_notional={max_order_notional:.2f} <= {max_order_notional_pct:.2%} * equity",
            )
        )
        checks.append(
            (
                total_notional <= equity * max_total_notional_pct,
                f"total_notional={total_notional:.2f} <= {max_total_notional_pct:.2%} * equity",
            )
        )

    if block_if_open_orders:
        checks.append((len(open_orders) == 0, f"open_orders={len(open_orders)} must be 0 before new submission"))

    reasons = [f"{message} [{'PASS' if passed else 'FAIL'}]" for passed, message in checks]
    return all(passed for passed, _ in checks), reasons


def reconcile_paper_portfolio_with_alpaca(
    paper_portfolio: pd.DataFrame,
    alpaca_positions: list[dict],
    share_tolerance: float = 1e-4,
) -> pd.DataFrame:
    """对账：比较本地模拟盘持仓和 Alpaca paper 持仓。

    为什么需要对账：
      本地 paper_portfolio 只是“我们以为应该持有多少”。
      Alpaca positions 是 broker 侧“实际成交后持有多少”。
      两者不一致时，可能是订单未成交、部分成交、被拒单，或者本地状态错误。
    """
    if paper_portfolio.empty:
        raise ValueError("paper_portfolio is empty")

    latest_run_id = paper_portfolio["run_id"].iloc[-1]
    local_latest = paper_portfolio.loc[paper_portfolio["run_id"] == latest_run_id].copy()
    local = {
        alpaca_symbol(str(row.symbol)): float(row.shares)
        for row in local_latest.itertuples(index=False)
        if abs(float(row.shares)) > share_tolerance
    }
    # Alpaca positions 里的 symbol 是 MSFT，不是 MSFT.US。
    broker = {str(position.get("symbol")): float(position.get("qty", 0.0)) for position in alpaca_positions}

    rows = []
    for symbol in sorted(set(local) | set(broker)):
        local_shares = float(local.get(symbol, 0.0))
        broker_shares = float(broker.get(symbol, 0.0))
        diff = broker_shares - local_shares
        rows.append(
            {
                "symbol": symbol,
                "local_shares": local_shares,
                "broker_shares": broker_shares,
                "diff_shares": diff,
                "matched": abs(diff) <= share_tolerance,
            }
        )
    return pd.DataFrame(rows)
