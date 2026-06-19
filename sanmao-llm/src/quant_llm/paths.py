from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def normalize_strategy_id(value: str) -> str:
    """把 market/strategy 名称规范成适合做目录名的字符串。

    为什么要有这个函数：
      不同市场、不同策略一定要写到不同目录，例如：
        models/us_sec_qwen_xgboost_v1/
        models/cn_a_baostock_price_xgboost_v1/

      如果大家都写到 models/latest_model.joblib，A 股运行一次就可能覆盖美股模型。
      所以目录名只保留字母、数字、下划线和短横线，避免路径里混入空格或特殊字符。
    """
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip())
    normalized = normalized.strip("_-").lower()
    if not normalized:
        raise ValueError("strategy_id cannot be empty after normalization")
    return normalized


def resolve_strategy_id(config: dict[str, Any], config_path: str | Path | None = None) -> str:
    """解析本次实验/策略的唯一 ID。

    优先级：
      1. YAML 里的 strategy_id。
      2. 如果没写 strategy_id，就用配置文件名兜底，例如 a_share_baostock.yaml。

    这样做是为了防止未来新增配置时忘记写 model_dir，仍然不会和其它市场共用模型目录。
    """
    configured = config.get("strategy_id")
    if configured:
        return normalize_strategy_id(str(configured))
    if config_path is None:
        raise ValueError("strategy_id is required when config_path is not provided")
    return normalize_strategy_id(Path(config_path).stem)


def resolve_model_dir(
    config: dict[str, Any],
    data_dir: str | Path,
    config_path: str | Path | None = None,
) -> Path:
    """解析模型保存目录，并强制按 strategy_id 隔离。

    规则：
      - 如果 YAML 显式写了 model_dir，就尊重 YAML。
      - 如果没写，就自动使用 <项目根目录>/models/<strategy_id>/。

    注意：
      旧代码默认写到 <项目根目录>/models/，这会导致不同市场共享
      latest_model.joblib。这里故意不再使用那个共享目录。
    """
    if config.get("model_dir"):
        return Path(str(config["model_dir"]))

    strategy_id = resolve_strategy_id(config, config_path)
    project_dir = Path(data_dir).parent
    return project_dir / "models" / strategy_id


def build_run_identity(config: dict[str, Any], config_path: str | Path | None = None) -> dict[str, str]:
    """返回写入报告和模型 metadata 的运行身份信息。

    market 用来区分 US / CN_A / HK。
    strategy_id 用来区分同一市场下的不同策略版本。
    """
    strategy_id = resolve_strategy_id(config, config_path)
    market = str(config.get("market") or config.get("paper_trading", {}).get("market") or "UNKNOWN")
    return {
        "market": market,
        "strategy_id": strategy_id,
    }


def validate_artifact_isolation(
    config: dict[str, Any],
    *,
    data_dir: str | Path,
    report_dir: str | Path,
    model_dir: str | Path,
    config_path: str | Path | None = None,
) -> None:
    """运行前检查产物目录是否按 strategy_id 隔离。

    这不是形式主义。量化工程里最怕的是：
      - A 股训练覆盖美股 training_features；
      - GDELT baseline 覆盖 Qwen baseline 的 metrics；
      - paper trading 加载了别的策略的 latest_model。

    所以生产级规则是：
      data_dir、report_dir、model_dir 三类目录都必须包含同一个 strategy_id。
      任何一个不满足就直接报错，不继续运行。
    """
    identity = build_run_identity(config, config_path)
    strategy_id = identity["strategy_id"]
    paths = {
        "data_dir": Path(data_dir),
        "report_dir": Path(report_dir),
        "model_dir": Path(model_dir),
    }
    for name, path in paths.items():
        if strategy_id not in path.parts:
            raise ValueError(
                f"{name} must include strategy_id '{strategy_id}' to avoid cross-strategy overwrite: {path}"
            )

    unique_paths = {str(path) for path in paths.values()}
    if len(unique_paths) != len(paths):
        raise ValueError(f"data_dir/report_dir/model_dir must be different directories: {paths}")
