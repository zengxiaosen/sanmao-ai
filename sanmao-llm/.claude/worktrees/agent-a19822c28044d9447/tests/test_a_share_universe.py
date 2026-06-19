from __future__ import annotations

import pandas as pd

from quant_llm.data import baostock_code_to_symbol


def test_baostock_code_to_symbol() -> None:
    assert baostock_code_to_symbol("sh.600000") == "600000.SH"
    assert baostock_code_to_symbol("sz.000001") == "000001.SZ"


def test_a_share_filtering_style_matches_basic_expectations() -> None:
    trade_date = "2026-05-29"
    as_of = pd.Timestamp(trade_date)
    frame = pd.DataFrame(
        {
            "code": ["sh.600000", "sz.000001", "sz.300001", "sh.600001"],
            "code_name": ["浦发银行", "*ST样本", "新股样本", "退市样本"],
            "ipoDate": pd.to_datetime(["1999-11-10", "1991-04-03", "2026-03-01", "2000-01-01"]),
            "outDate": [pd.NaT, pd.NaT, pd.NaT, as_of - pd.Timedelta(days=1)],
            "type": ["1", "1", "1", "1"],
            "status": ["1", "1", "1", "1"],
            "symbol": ["600000.SH", "000001.SZ", "300001.SZ", "600001.SH"],
        }
    )

    filtered = frame.copy()
    filtered = filtered[filtered["type"] == "1"]
    filtered = filtered[filtered["status"] == "1"]
    filtered = filtered[(as_of - filtered["ipoDate"]).dt.days >= 120]
    filtered = filtered[filtered["outDate"].isna() | (filtered["outDate"] > as_of)]
    filtered = filtered[~filtered["code_name"].fillna("").str.contains("ST", case=False, regex=False)]

    assert filtered["symbol"].tolist() == ["600000.SH"]
