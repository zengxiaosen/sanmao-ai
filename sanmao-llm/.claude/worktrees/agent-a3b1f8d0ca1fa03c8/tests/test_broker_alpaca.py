from __future__ import annotations

import pandas as pd
import pytest

from quant_llm.brokers.alpaca import AlpacaConfig, AlpacaTradingClient, alpaca_symbol


def test_alpaca_symbol_removes_us_suffix() -> None:
    assert alpaca_symbol("AAPL.US") == "AAPL"
    assert alpaca_symbol("SPY") == "SPY"


def test_alpaca_client_refuses_live_url_by_default() -> None:
    config = AlpacaConfig(
        api_key_id="key",
        api_secret_key="secret",
        base_url="https://api.alpaca.markets",
        allow_live_trading=False,
    )

    with pytest.raises(ValueError, match="Refusing non-paper"):
        AlpacaTradingClient(config)


def test_submit_script_detects_already_submitted_run(tmp_path) -> None:
    import importlib.util
    from pathlib import Path

    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run" / "submit_alpaca_paper_orders.py"
    spec = importlib.util.spec_from_file_location("submit_alpaca_paper_orders", script_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    result_path = tmp_path / "broker_order_results.csv"
    pd.DataFrame(
        {
            "run_id": ["r1"],
            "symbol": ["MSFT.US"],
            "submitted": [True],
        }
    ).to_csv(result_path, index=False)

    assert module._already_submitted(result_path, "r1") is True
    assert module._already_submitted(result_path, "r2") is False
