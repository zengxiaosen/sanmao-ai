from __future__ import annotations

import pytest

from quant_llm.market_rules import CHINA_A_RULES, US_EQUITY_RULES, market_rules_from_name


def test_us_market_allows_fractional_shares() -> None:
    assert US_EQUITY_RULES.round_target_shares(12.3456, side="buy") == 12.3456


def test_china_a_market_rounds_down_to_lot_size() -> None:
    assert CHINA_A_RULES.round_target_shares(256.7, side="buy") == 200.0
    assert CHINA_A_RULES.round_target_shares(99.9, side="buy") == 0.0


def test_market_rules_from_name_aliases() -> None:
    assert market_rules_from_name("alpaca").market == "US"
    assert market_rules_from_name("china_a").market == "CN_A"
    assert market_rules_from_name("hk").market == "HK"


def test_market_rules_from_name_rejects_unknown_market() -> None:
    with pytest.raises(ValueError):
        market_rules_from_name("unknown")
