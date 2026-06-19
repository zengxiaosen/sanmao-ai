from __future__ import annotations

from pathlib import Path

import pytest

from quant_llm.config import load_config


def test_load_config_expands_symbols_file_relative_to_config(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    symbols_path = config_dir / "cn_a_symbols.txt"
    symbols_path.write_text("600000.SH\n# comment\n\n000001.SZ\n", encoding="utf-8")

    config_path = config_dir / "a_share.yaml"
    config_path.write_text("market: CN_A\nsymbols_file: cn_a_symbols.txt\n", encoding="utf-8")

    config = load_config(config_path)

    assert config["symbols"] == ["600000.SH", "000001.SZ"]
    assert config["symbols_file"] == str(symbols_path.resolve())


def test_load_config_rejects_empty_symbols_file(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    symbols_path = config_dir / "empty.txt"
    symbols_path.write_text("# only comments\n\n", encoding="utf-8")

    config_path = config_dir / "a_share.yaml"
    config_path.write_text("market: CN_A\nsymbols_file: empty.txt\n", encoding="utf-8")

    with pytest.raises(ValueError, match="symbols_file is empty"):
        load_config(config_path)
