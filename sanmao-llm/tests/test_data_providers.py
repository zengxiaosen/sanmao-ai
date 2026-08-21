from __future__ import annotations

import pandas as pd

from quant_llm.data import PriceSource
from quant_llm.macro import _parse_fred_csv


def test_parse_tencent_payload_extracts_rows(tmp_path) -> None:
    source = PriceSource(tmp_path, provider="tencent")
    payload = {
        "code": 0,
        "data": {
            "usNVDA.OQ": {
                "qfqday": [
                    ["2026-08-15", "182.01", "183.16", "184.48", "181.40", "155376450.00"],
                    ["2026-08-18", "183.09", "182.15", "183.98", "181.61", "128762310.00"],
                ]
            }
        },
    }
    rows = PriceSource._parse_tencent_payload(payload, "usNVDA.OQ")
    assert len(rows) == 2
    # 腾讯行格式：[date, open, close, high, low, volume]
    assert rows[0][0] == "2026-08-15"
    assert rows[0][2] == "183.16"
    assert source.provider == "tencent"


def test_parse_tencent_payload_handles_missing_symbol() -> None:
    assert PriceSource._parse_tencent_payload({"data": {}}, "usXXX.OQ") == []
    assert PriceSource._parse_tencent_payload({"data": []}, "usXXX.OQ") == []
    assert PriceSource._parse_tencent_payload({}, "usXXX.OQ") == []


def test_parse_fred_csv_skips_missing_values() -> None:
    text = "observation_date,VIXCLS\n2026-08-03,15.86\n2026-08-04,.\n2026-08-05,16.50\n"
    series = _parse_fred_csv(text, "vix")
    assert series.name == "vix"
    assert len(series) == 2  # "." 缺失行被丢掉
    assert float(series.iloc[0]) == 15.86
    assert isinstance(series.index, pd.DatetimeIndex)
