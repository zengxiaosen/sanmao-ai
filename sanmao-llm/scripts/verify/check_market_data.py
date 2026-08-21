from __future__ import annotations

import argparse
import json

from quant_llm.data import load_price_panel
from quant_llm.config import load_project_env


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether a market data provider returns real OHLCV rows.")
    parser.add_argument("--provider", default="yfinance", choices=["yfinance", "yahoo_chart", "alpha_vantage", "tiingo", "synthetic"])
    parser.add_argument("--symbol", default="AAPL.US")
    parser.add_argument("--start-date", default="2024-01-01")
    parser.add_argument("--end-date", default="2024-03-31")
    parser.add_argument("--data-dir", default="/root/sanmao-ai/sanmao-llm/data/checks")
    parser.add_argument("--allow-synthetic-fallback", action="store_true")
    args = parser.parse_args()

    load_project_env()
    frame = load_price_panel(
        [args.symbol],
        args.start_date,
        args.end_date,
        args.data_dir,
        allow_synthetic_fallback=args.allow_synthetic_fallback,
        provider=args.provider,
    )
    provider_used = sorted(frame["data_provider_used"].dropna().unique().tolist())
    real_providers = {"yfinance", "yahoo_chart", "alpha_vantage", "tiingo"}
    is_real_market_data = bool(provider_used) and all(provider in real_providers for provider in provider_used)
    summary = {
        "symbol": args.symbol,
        "requested_provider": args.provider,
        "provider_used": provider_used,
        "rows": int(len(frame)),
        "start": str(frame["date"].min().date()),
        "end": str(frame["date"].max().date()),
        "last_close": float(frame["close"].iloc[-1]),
        "is_real_market_data": is_real_market_data,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if not summary["is_real_market_data"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
