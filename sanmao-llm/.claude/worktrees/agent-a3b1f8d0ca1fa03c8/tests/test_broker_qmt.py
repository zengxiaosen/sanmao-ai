from __future__ import annotations

import pytest

from quant_llm.brokers.qmt import QmtConfig, QmtTradingClient, check_qmt_environment


def test_check_qmt_environment_reports_missing_requirements(tmp_path) -> None:
    result = check_qmt_environment(
        QmtConfig(
            account_id="",
            client_path=str(tmp_path / "missing_qmt"),
            trading_mode="paper",
        )
    )

    assert result["account_id_configured"] is False
    assert result["client_path_exists"] is False
    assert result["ready_for_qmt_connection"] is False


def test_qmt_client_rejects_live_trading_mode() -> None:
    with pytest.raises(ValueError, match="live trading is disabled"):
        QmtTradingClient(QmtConfig(account_id="demo", trading_mode="live"))
