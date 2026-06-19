from __future__ import annotations

import pytest

from quant_llm.brokers.futu import FutuConfig, FutuTradingClient, check_futu_opend_environment


def test_check_futu_opend_environment_reports_missing_opend() -> None:
    result = check_futu_opend_environment(
        FutuConfig(
            host="127.0.0.1",
            port=9,
            trading_mode="paper",
            market="HK",
        ),
        timeout_seconds=0.1,
    )

    assert result["opend_tcp_connected"] is False
    assert result["ready_for_futu_connection"] is False


def test_futu_client_rejects_live_trading_mode() -> None:
    with pytest.raises(ValueError, match="live trading is disabled"):
        FutuTradingClient(FutuConfig(trading_mode="live"))
