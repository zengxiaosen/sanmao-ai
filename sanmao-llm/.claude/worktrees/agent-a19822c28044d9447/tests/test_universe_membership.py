from __future__ import annotations

from pathlib import Path

import pandas as pd

from quant_llm.data import apply_universe_membership, load_universe_membership


def test_load_universe_membership_requires_date_and_symbol(tmp_path: Path) -> None:
    path = tmp_path / "membership.csv"
    path.write_text("date,symbol\n2024-01-02,000001.SZ\n", encoding="utf-8")

    frame = load_universe_membership(path)

    assert frame["symbol"].tolist() == ["000001.SZ"]
    assert str(frame["date"].iloc[0].date()) == "2024-01-02"


def test_apply_universe_membership_filters_price_rows() -> None:
    prices = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-02", "2024-01-03"]),
            "symbol": ["000001.SZ", "000002.SZ", "000001.SZ"],
            "close": [10.0, 20.0, 11.0],
        }
    )
    membership = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-03"]),
            "symbol": ["000001.SZ", "000001.SZ"],
        }
    )

    filtered = apply_universe_membership(prices, membership)

    assert filtered["symbol"].tolist() == ["000001.SZ", "000001.SZ"]
    assert filtered["close"].tolist() == [10.0, 11.0]
