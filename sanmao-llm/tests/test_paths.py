from __future__ import annotations

from pathlib import Path

import pytest

from quant_llm.paths import build_run_identity, resolve_model_dir, resolve_strategy_id, validate_artifact_isolation


def test_explicit_model_dirs_keep_markets_isolated() -> None:
    """显式 model_dir 时，美股和 A 股不能落到同一个 latest_model 目录。"""
    us_config = {
        "market": "US",
        "strategy_id": "us_sec_qwen_xgboost_v1",
        "model_dir": "/project/models/us_sec_qwen_xgboost_v1",
    }
    a_share_config = {
        "market": "CN_A",
        "strategy_id": "cn_a_baostock_price_xgboost_v1",
        "model_dir": "/project/models/cn_a_baostock_price_xgboost_v1",
    }

    us_model_dir = resolve_model_dir(us_config, "/project/data", "config/sec_filings_qwen.yaml")
    a_share_model_dir = resolve_model_dir(a_share_config, "/project/data_a_share", "config/a_share_baostock.yaml")

    assert us_model_dir != a_share_model_dir
    assert us_model_dir / "latest_model.joblib" != a_share_model_dir / "latest_model.joblib"


def test_missing_model_dir_falls_back_to_strategy_subdirectory() -> None:
    """没写 model_dir 时，也不能回退到共享 /models/latest_model.joblib。"""
    config = {
        "market": "HK",
        "strategy_id": "hk_futu_placeholder_v1",
    }

    model_dir = resolve_model_dir(config, "/project/data_hk", "config/hk_futu.yaml")

    assert model_dir == Path("/project/models/hk_futu_placeholder_v1")
    assert model_dir != Path("/project/models")


def test_missing_strategy_id_uses_config_file_stem() -> None:
    """忘记写 strategy_id 时，用配置文件名兜底，避免不同配置互相覆盖。"""
    config = {
        "market": "US",
    }

    assert resolve_strategy_id(config, "config/sec_filings_qwen.yaml") == "sec_filings_qwen"
    assert resolve_model_dir(config, "/project/data", "config/sec_filings_qwen.yaml") == Path(
        "/project/models/sec_filings_qwen"
    )


def test_run_identity_records_market_and_strategy() -> None:
    """metadata/metrics 里要写清楚这个模型属于哪个市场、哪个策略。"""
    identity = build_run_identity({"market": "CN_A", "strategy_id": "cn_a_test_v1"}, "config/a_share.yaml")

    assert identity == {
        "market": "CN_A",
        "strategy_id": "cn_a_test_v1",
    }


def test_strategy_artifact_roots_are_not_shared() -> None:
    """生产级隔离要求：data/report/model 三类目录都应该带 strategy_id。"""
    strategy_id = "us_sec_qwen_xgboost_v1"
    config = {
        "market": "US",
        "strategy_id": strategy_id,
        "data_dir": f"/project/data/{strategy_id}",
        "report_dir": f"/project/reports/{strategy_id}",
        "model_dir": f"/project/models/{strategy_id}",
    }

    assert Path(config["data_dir"]).name == strategy_id
    assert Path(config["report_dir"]).name == strategy_id
    assert Path(config["model_dir"]).name == strategy_id


def test_validate_artifact_isolation_rejects_shared_legacy_dirs() -> None:
    """旧式共享目录必须被运行时拦截，不能继续写入。"""
    config = {
        "market": "US",
        "strategy_id": "us_sec_qwen_xgboost_v1",
    }

    with pytest.raises(ValueError, match="must include strategy_id"):
        validate_artifact_isolation(
            config,
            data_dir="/project/data",
            report_dir="/project/reports",
            model_dir="/project/models/us_sec_qwen_xgboost_v1",
            config_path="config/sec_filings_qwen.yaml",
        )


def test_validate_artifact_isolation_accepts_strategy_scoped_dirs() -> None:
    strategy_id = "us_sec_qwen_xgboost_v1"
    config = {
        "market": "US",
        "strategy_id": strategy_id,
    }

    validate_artifact_isolation(
        config,
        data_dir=f"/project/data/{strategy_id}",
        report_dir=f"/project/reports/{strategy_id}",
        model_dir=f"/project/models/{strategy_id}",
        config_path="config/sec_filings_qwen.yaml",
    )
