from __future__ import annotations

import argparse

from quant_llm.config import load_project_env
from quant_llm.news import fetch_sec_filings, save_news_csv


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch free SEC EDGAR filings into the project news CSV schema.")
    parser.add_argument("--symbols", nargs="+", default=["AAPL.US", "MSFT.US", "NVDA.US"])
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--forms", nargs="+", default=["8-K", "10-Q", "10-K"])
    parser.add_argument("--limit-per-symbol", type=int, default=50)
    parser.add_argument("--output", default="/root/sanmao-ai/sanmao-llm/data/us_sec_rule_text_xgboost_v1/news/sec_filings.csv")
    args = parser.parse_args()

    load_project_env()
    filings = fetch_sec_filings(
        args.symbols,
        args.start_date,
        args.end_date,
        forms=args.forms,
        limit_per_symbol=args.limit_per_symbol,
    )
    save_news_csv(filings, args.output)
    print(f"saved {len(filings)} SEC filing rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
