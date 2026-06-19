from __future__ import annotations

import pandas as pd

from quant_llm.news import DEFAULT_SYMBOL_QUERIES, fetch_sec_filings, save_news_csv


def test_save_news_csv_creates_parent_directory(tmp_path) -> None:
    output = tmp_path / "nested" / "news.csv"
    frame = pd.DataFrame(
        {
            "date": ["2024-01-01"],
            "symbol": ["AAPL.US"],
            "title": ["title"],
            "body": ["body"],
        }
    )

    save_news_csv(frame, output)

    assert output.exists()


def test_fetch_sec_filings_empty_date_range() -> None:
    frame = fetch_sec_filings(["AAPL.US"], "1900-01-01", "1900-01-31")

    assert frame.empty
    assert {"date", "symbol", "title", "body", "source", "url", "tags"}.issubset(frame.columns)


def test_default_gdelt_queries_cover_baseline_symbols() -> None:
    assert {"AAPL.US", "MSFT.US", "NVDA.US", "SPY.US"}.issubset(DEFAULT_SYMBOL_QUERIES)
