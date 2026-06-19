from __future__ import annotations

import argparse

from quant_llm.config import load_project_env
from quant_llm.news import fetch_tiingo_news, save_news_csv


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch Tiingo News into the CSV schema used by text_features.py.")
    parser.add_argument("--symbols", nargs="+", default=["AAPL.US", "MSFT.US", "NVDA.US", "SPY.US"])
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--output", default="/root/autodl-tmp/sanmao-quant-llm/data/us_tiingo_news_raw/news/tiingo_news.csv")
    args = parser.parse_args()

    load_project_env()
    news = fetch_tiingo_news(args.symbols, args.start_date, args.end_date, limit=args.limit)
    save_news_csv(news, args.output)
    print(f"saved {len(news)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
