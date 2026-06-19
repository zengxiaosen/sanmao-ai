from __future__ import annotations

import pandas as pd

from quant_llm.text_features import (
    TEXT_FEATURE_COLUMNS,
    build_daily_text_features,
    extract_text_events,
    join_text_features,
)


def test_text_events_aggregate_and_join_to_price_features() -> None:
    news = pd.DataFrame(
        {
            "date": ["2024-01-02", "2024-01-02"],
            "symbol": ["AAPL.US", "AAPL.US"],
            "title": ["Apple earnings beat", "Apple warns on margin pressure"],
            "body": ["Strong revenue growth.", "Risk of margin pressure remains."],
        }
    )
    events = extract_text_events(news)
    daily = build_daily_text_features(events)

    assert daily.loc[0, "llm_news_count"] == 2
    assert daily.loc[0, "event_earnings_count"] >= 1
    assert daily.loc[0, "risk_margin_pressure_count"] >= 1

    price_features = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-03"]),
            "symbol": ["AAPL.US", "AAPL.US"],
            "ret_1d": [0.01, 0.02],
        }
    )
    joined = join_text_features(price_features, daily)

    assert set(TEXT_FEATURE_COLUMNS).issubset(joined.columns)
    assert joined.loc[0, "llm_news_count"] == 2
    assert joined.loc[1, "llm_news_count"] == 0

