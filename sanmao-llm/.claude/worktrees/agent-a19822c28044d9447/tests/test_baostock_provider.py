from __future__ import annotations

from pathlib import Path

import pytest

from quant_llm.data import PriceSource


def test_baostock_symbol_conversion() -> None:
    source = PriceSource(Path("/tmp/sanmao-test"))

    assert source._baostock_symbol("600000.SH") == "sh.600000"
    assert source._baostock_symbol("000001.SZ") == "sz.000001"
    assert source._baostock_symbol("sh.600000") == "sh.600000"


def test_baostock_symbol_rejects_non_a_share_symbol() -> None:
    source = PriceSource(Path("/tmp/sanmao-test"))

    with pytest.raises(ValueError, match="BaoStock symbol"):
        source._baostock_symbol("AAPL.US")
