from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from quant_llm.market_rules import MarketRules, market_rules_from_name


def load_latest_model(model_dir: str | Path):
    """加载通过回测晋级门槛的 latest_model。

    paper trading 只能默认加载 latest_model.joblib，而不是 candidate_model.joblib。
    原因：
      candidate_model 只是“本次跑出来的候选模型”；
      latest_model 是通过 model_promotion 门槛后才允许覆盖的模型。

    如果 latest_model 不存在，说明还没有任何候选模型通过回测门槛。
    这种情况下应该停止模拟盘，而不是偷偷拿 candidate_model 去跑。
    """
    model_dir = Path(model_dir)
    model_path = model_dir / "latest_model.joblib"
    metadata_path = model_dir / "latest_model_metadata.json"
    if not model_path.exists():
        raise FileNotFoundError(f"Missing {model_path}. Run run_all.sh and pass model_promotion first.")
    if not metadata_path.exists():
        raise FileNotFoundError(f"Missing {metadata_path}. latest_model metadata is required for feature columns.")

    model = joblib.load(model_path)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    return model, metadata


def build_latest_signals(
    training_features: pd.DataFrame,
    model,
    feature_columns: list[str],
    threshold: float,
) -> pd.DataFrame:
    """用最新一天的特征生成模拟盘信号。

    输入的 training_features 是训练/回测链路已经生成好的最终特征表。
    这里不重新发明特征，只复用训练时同一批 feature_columns，避免训练和应用不一致。

    输出字段：
      date:
        信号日期。当前是日线收盘后信号，语义是“用这天收盘后可见的数据生成建议”。
      symbol:
        股票代码。
      close:
        当前用于估值/模拟成交的价格。第一版用收盘价近似成交价。
      prob_up:
        模型认为下一期上涨的概率。
      target_position:
        1 表示希望持有，0 表示希望空仓。
      action:
        long / flat，方便人读。
    """
    missing = [column for column in feature_columns if column not in training_features.columns]
    if missing:
        raise ValueError(f"training_features missing model feature columns: {missing}")

    latest_date = training_features["date"].max()
    latest = training_features.loc[training_features["date"] == latest_date].copy()
    if latest.empty:
        raise ValueError("No latest rows available in training_features")

    prob_up = np.asarray(model.predict_proba(latest[feature_columns]))[:, 1]
    latest["prob_up"] = prob_up
    latest["target_position"] = (latest["prob_up"] >= threshold).astype(float)
    latest["action"] = latest["target_position"].map({1.0: "long", 0.0: "flat"})

    return latest[["date", "symbol", "close", "prob_up", "target_position", "action"]].sort_values("symbol").reset_index(drop=True)


def _latest_cash_and_holdings(portfolio_path: Path, starting_cash: float) -> tuple[float, dict[str, float]]:
    """读取上一轮模拟盘状态。

    portfolio_path 不存在时，代表第一次跑模拟盘：
      cash = starting_cash
      holdings = 空
    """
    if not portfolio_path.exists():
        return float(starting_cash), {}

    history = pd.read_csv(portfolio_path)
    if history.empty:
        return float(starting_cash), {}

    latest_run = history["run_id"].iloc[-1]
    latest = history.loc[history["run_id"] == latest_run]
    cash_values = latest["cash"].dropna().unique()
    cash = float(cash_values[-1]) if len(cash_values) else float(starting_cash)
    holdings = dict(zip(latest["symbol"], latest["shares"]))
    return cash, {symbol: float(shares) for symbol, shares in holdings.items()}


def run_paper_account_update(
    signals: pd.DataFrame,
    output_dir: str | Path,
    starting_cash: float = 100_000.0,
    max_symbol_weight: float = 0.25,
    transaction_cost_bps: float = 5.0,
    market_rules: MarketRules | None = None,
) -> dict:
    """根据最新信号更新模拟账户。

    第一版 paper trading 的原则：
      1. 不接券商，不发真实订单。
      2. 用 close 作为模拟成交价，后续再加入更真实的成交价/滑点。
      3. long 的股票等权配置，并受 max_symbol_weight 限制。
      4. flat 的股票目标仓位是 0。
      5. 股数会经过 market_rules 取整：美股可小数股，A 股按 100 股一手。

    输出文件：
      paper_orders.csv:
        每次模拟调仓产生的订单流水。
      paper_portfolio.csv:
        每次运行后的持仓快照。
      paper_summary.json:
        最新一次模拟账户摘要。
    """
    output_dir = Path(output_dir)
    market_rules = market_rules or market_rules_from_name("US")
    output_dir.mkdir(parents=True, exist_ok=True)
    orders_path = output_dir / "paper_orders.csv"
    portfolio_path = output_dir / "paper_portfolio.csv"
    summary_path = output_dir / "paper_summary.json"

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    cash, previous_shares = _latest_cash_and_holdings(portfolio_path, starting_cash)

    price_by_symbol = dict(zip(signals["symbol"], signals["close"]))
    previous_value = sum(previous_shares.get(symbol, 0.0) * float(price) for symbol, price in price_by_symbol.items())
    equity_before = float(cash + previous_value)

    long_symbols = signals.loc[signals["target_position"] > 0, "symbol"].tolist()
    if long_symbols:
        equal_weight = min(float(max_symbol_weight), 1.0 / len(long_symbols))
    else:
        equal_weight = 0.0

    orders = []
    new_shares: dict[str, float] = {}
    total_cost = 0.0
    for row in signals.itertuples(index=False):
        symbol = row.symbol
        close = float(row.close)
        target_weight = equal_weight if float(row.target_position) > 0 else 0.0
        target_value = equity_before * target_weight
        raw_target_shares = target_value / close if close > 0 else 0.0
        target_shares = market_rules.round_target_shares(
            raw_target_shares,
            side="buy" if float(row.target_position) > 0 else "sell",
        )
        current_shares = previous_shares.get(symbol, 0.0)
        delta_shares = target_shares - current_shares
        notional = delta_shares * close
        transaction_cost = abs(notional) * float(transaction_cost_bps) / 10_000.0

        total_cost += transaction_cost
        cash -= notional + transaction_cost
        new_shares[symbol] = target_shares

        orders.append(
            {
                "run_id": run_id,
                "signal_date": row.date,
                "symbol": symbol,
                "action": "buy" if delta_shares > 0 else "sell" if delta_shares < 0 else "hold",
                "target_position": float(row.target_position),
                "prob_up": float(row.prob_up),
                "fill_price": close,
                "delta_shares": delta_shares,
                "notional": notional,
                "transaction_cost": transaction_cost,
            }
        )

    portfolio_rows = []
    equity_after = cash
    for row in signals.itertuples(index=False):
        symbol = row.symbol
        close = float(row.close)
        shares = new_shares.get(symbol, 0.0)
        market_value = shares * close
        equity_after += market_value
        portfolio_rows.append(
            {
                "run_id": run_id,
                "signal_date": row.date,
                "symbol": symbol,
                "shares": shares,
                "close": close,
                "market_value": market_value,
                "cash": cash,
            }
        )

    orders_frame = pd.DataFrame(orders)
    portfolio_frame = pd.DataFrame(portfolio_rows)

    if orders_path.exists():
        orders_frame.to_csv(orders_path, mode="a", header=False, index=False)
    else:
        orders_frame.to_csv(orders_path, index=False)

    if portfolio_path.exists():
        portfolio_frame.to_csv(portfolio_path, mode="a", header=False, index=False)
    else:
        portfolio_frame.to_csv(portfolio_path, index=False)

    summary = {
        "run_id": run_id,
        "signal_date": str(pd.Timestamp(signals["date"].max()).date()),
        "equity_before": equity_before,
        "equity_after": equity_after,
        "cash": cash,
        "total_transaction_cost": total_cost,
        "long_count": len(long_symbols),
        "market": market_rules.market,
        "lot_size": market_rules.lot_size,
        "allow_fractional_shares": market_rules.allow_fractional_shares,
        "orders_path": str(orders_path),
        "portfolio_path": str(portfolio_path),
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary
