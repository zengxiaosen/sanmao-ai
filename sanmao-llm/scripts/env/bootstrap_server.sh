#!/usr/bin/env bash
set -euo pipefail

# 创建/更新 sanmao-quant-llm 的运行环境（本机）。
# 用法：
#   cd /root/sanmao-ai/sanmao-llm
#   bash scripts/env/bootstrap_server.sh
#
# 说明：
#   - 本工程只用传统 ML（lightgbm/xgboost/scikit-learn），不需要 GPU、不需要 PyTorch。
#   - LLM 文本抽取走 Claude API（anthropic SDK），只需要一个 ANTHROPIC_API_KEY。
#   - 需要 Python >= 3.10 来创建 .venv。

PROJECT_DIR="${PROJECT_DIR:-/srv/dev/web-ui/sanmao-llm}"
# 用于创建 .venv 的解释器，必须是 Python >= 3.10。可用环境变量覆盖，例如 PYTHON_BIN=python3.11。
PYTHON_BIN="${PYTHON_BIN:-python3}"

cd "$PROJECT_DIR"

mkdir -p data reports logs models

if [[ ! -x .venv/bin/python ]]; then
  "$PYTHON_BIN" -m venv .venv
fi

.venv/bin/python -m pip install --upgrade pip setuptools wheel
# 安装量化核心依赖 + LLM 抽取用的 anthropic + 测试用 pytest。
# 如果只想跑价格特征/回测、不跑 LLM 抽取，可以去掉 '.[llm]' 只装 '.'。
.venv/bin/pip install -e '.[llm]' pytest

echo "Environment ready: $PROJECT_DIR/.venv"
echo "Set your key first: export ANTHROPIC_API_KEY=... (or put it in .env)"
echo "Run tests with: .venv/bin/pytest -q"
echo "Run baseline with: .venv/bin/python scripts/run/run_baseline.py --config config/baseline.yaml"
