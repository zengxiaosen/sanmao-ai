from __future__ import annotations

import pandas as pd

from quant_llm.data import baostock_code_to_symbol


def test_baostock_membership_symbol_conversion() -> None:
    assert baostock_code_to_symbol("sh.600000") == "600000.SH"
    assert baostock_code_to_symbol("sz.000001") == "000001.SZ"


def test_historical_membership_shape_expectation() -> None:
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2021-01-04", "2021-01-04", "2021-01-05"]),
            "symbol": ["600000.SH", "600004.SH", "600000.SH"],
        }
    )
    deduped = frame.drop_duplicates().sort_values(["date", "symbol"]).reset_index(drop=True)

    assert len(deduped) == 3
    assert deduped.iloc[0]["symbol"] == "600000.SH"
