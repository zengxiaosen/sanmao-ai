from __future__ import annotations

import pandas as pd

from quant_llm.llm_extractor import parse_llm_event_json


def test_parse_llm_event_json_extracts_text_event() -> None:
    row = pd.Series({"date": "2024-01-02", "symbol": "AAPL.US"})
    event = parse_llm_event_json(
        '{"event_type":"earnings","sentiment":0.4,"confidence":0.8,"impact_horizon":"1-5d","risk_tags":["guidance"]}',
        row,
    )

    assert event.symbol == "AAPL.US"
    assert event.event_type == "earnings"
    assert event.sentiment == 0.4
    assert event.risk_tags == ("guidance",)


def test_parse_llm_event_json_clips_scores_and_normalizes_categories() -> None:
    row = pd.Series({"date": "2024-01-02", "symbol": "AAPL.US"})
    event = parse_llm_event_json(
        '{"event_type":"rumor","sentiment":2.4,"confidence":-0.3,"impact_horizon":"next decade","risk_tags":"unclear"}',
        row,
    )

    assert event.event_type == "other"
    assert event.sentiment == 1.0
    assert event.confidence == 0.0
    assert event.impact_horizon == "1-5d"
    assert event.risk_tags == ("unclear",)
