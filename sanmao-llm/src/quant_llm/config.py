from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


def load_project_env(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if env_path.exists():
        load_dotenv(env_path)


def _load_symbols_file(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"symbols_file not found: {path}")

    symbols: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        symbols.append(line)
    if not symbols:
        raise ValueError(f"symbols_file is empty: {path}")
    return symbols


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    if not isinstance(config, dict):
        raise ValueError(f"Config must be a mapping: {path}")

    if "symbols_file" in config:
        symbols_path = Path(str(config["symbols_file"]))
        if not symbols_path.is_absolute():
            symbols_path = (config_path.parent / symbols_path).resolve()
        config["symbols"] = _load_symbols_file(symbols_path)
        config["symbols_file"] = str(symbols_path)

    if "universe_membership_csv" in config:
        membership_path = Path(str(config["universe_membership_csv"]))
        if not membership_path.is_absolute():
            membership_path = (config_path.parent / membership_path).resolve()
        config["universe_membership_csv"] = str(membership_path)
    return config
