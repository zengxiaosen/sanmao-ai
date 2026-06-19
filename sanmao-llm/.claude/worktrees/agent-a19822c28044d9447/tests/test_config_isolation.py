from __future__ import annotations

from pathlib import Path

import yaml


CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


def _load_strategy_configs() -> list[tuple[Path, dict]]:
    configs: list[tuple[Path, dict]] = []
    for path in sorted(CONFIG_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "strategy_id" in data:
            configs.append((path, data))
    return configs


def test_strategy_configs_have_unique_artifact_roots() -> None:
    """每个策略必须拥有独立 data/report/model 目录，防止互相覆盖。"""
    configs = _load_strategy_configs()
    assert configs, "No strategy configs found"

    seen: dict[str, tuple[str, Path]] = {}
    for path, config in configs:
        strategy_id = str(config["strategy_id"])
        for key in ["data_dir", "report_dir", "model_dir"]:
            assert key in config, f"{path.name} missing {key}"
            artifact_path = str(config[key])
            assert strategy_id in Path(artifact_path).parts, f"{path.name} {key} must include strategy_id"

            # 同一个目录不能被两个策略共用。否则 metrics、training_features、latest_model 会互相覆盖。
            if artifact_path in seen:
                previous_key, previous_path = seen[artifact_path]
                raise AssertionError(
                    f"{path.name} {key} shares {artifact_path} with {previous_path.name} {previous_key}"
                )
            seen[artifact_path] = (key, path)


def test_paper_trading_outputs_are_strategy_scoped() -> None:
    """模拟盘输出也必须在各自 report_dir 下，不能共用 reports/paper_trading。"""
    for path, config in _load_strategy_configs():
        paper_config = config.get("paper_trading")
        if not paper_config:
            continue

        output_dir = Path(str(paper_config["output_dir"]))
        report_dir = Path(str(config["report_dir"]))

        assert str(output_dir).startswith(str(report_dir)), f"{path.name} paper output must live under report_dir"
        assert output_dir.name == "paper_trading"
