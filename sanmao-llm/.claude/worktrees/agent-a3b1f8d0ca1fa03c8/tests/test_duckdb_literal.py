from __future__ import annotations

import importlib.util
from pathlib import Path


def test_duckdb_string_literal_escapes_quotes() -> None:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run" / "run_baseline.py"
    spec = importlib.util.spec_from_file_location("run_baseline", script_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    assert module.duckdb_string_literal("/tmp/a'b.parquet") == "'/tmp/a''b.parquet'"


def test_model_promotion_gate_blocks_bad_backtest() -> None:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run" / "run_baseline.py"
    spec = importlib.util.spec_from_file_location("run_baseline", script_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    promoted, reasons = module.passes_model_promotion_gate(
        {
            "annual_return": -0.10,
            "sharpe": -0.20,
            "max_drawdown": -0.40,
            "mean_daily_turnover": 0.30,
        },
        {
            "enabled": True,
            "min_annual_return": 0.0,
            "min_sharpe": 0.0,
            "min_max_drawdown": -0.25,
            "max_mean_daily_turnover": 1.0,
        },
    )

    assert promoted is False
    assert any("annual_return" in reason and "FAIL" in reason for reason in reasons)
    assert any("max_drawdown" in reason and "FAIL" in reason for reason in reasons)


def test_model_promotion_gate_allows_good_backtest() -> None:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run" / "run_baseline.py"
    spec = importlib.util.spec_from_file_location("run_baseline", script_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    promoted, reasons = module.passes_model_promotion_gate(
        {
            "annual_return": 0.05,
            "sharpe": 0.30,
            "max_drawdown": -0.12,
            "mean_daily_turnover": 0.30,
        },
        {
            "enabled": True,
            "min_annual_return": 0.0,
            "min_sharpe": 0.0,
            "min_max_drawdown": -0.25,
            "max_mean_daily_turnover": 1.0,
        },
    )

    assert promoted is True
    assert all("FAIL" not in reason for reason in reasons)
