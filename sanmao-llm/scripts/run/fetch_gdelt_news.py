from __future__ import annotations

import argparse

from quant_llm.news import fetch_gdelt_news, save_news_csv


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch free GDELT news into the project news CSV schema.")
    parser.add_argument("--symbols", nargs="+", default=["AAPL.US", "MSFT.US", "NVDA.US", "SPY.US"])
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--maxrecords-per-symbol", type=int, default=20)
    parser.add_argument(
        "--output",
        default="/root/sanmao-ai/sanmao-llm/data/us_gdelt_rule_text_xgboost_v1/news/gdelt_news.csv",
    )
    args = parser.parse_args()

    news = fetch_gdelt_news(
        args.symbols,
        args.start_date,
        args.end_date,
        maxrecords_per_symbol=args.maxrecords_per_symbol,
    )
    save_news_csv(news, args.output)
    print(f"saved {len(news)} GDELT news rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
