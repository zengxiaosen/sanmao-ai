#!/usr/bin/env bash
set -euo pipefail

# 服务器重启/关机后，用这个脚本恢复 sanmao-quant-llm 的运行环境。
# 用法：
#   ssh seeta-gpu
#   cd /root/autodl-tmp/sanmao-quant-llm
#   bash scripts/env/bootstrap_server.sh

PROJECT_DIR="${PROJECT_DIR:-/root/autodl-tmp/sanmao-quant-llm}"
PYTHON_BIN="${PYTHON_BIN:-/root/miniconda3/bin/python}"

cd "$PROJECT_DIR"

mkdir -p data reports logs models

if [[ ! -x .venv/bin/python ]]; then
  "$PYTHON_BIN" -m venv .venv
fi

.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/pip install -e . pytest

echo "Environment ready: $PROJECT_DIR/.venv"
echo "Run tests with: .venv/bin/pytest -q"
echo "Run baseline with: .venv/bin/python scripts/run/run_baseline.py --config config/baseline.yaml"

