#!/usr/bin/env bash
set -euo pipefail

# verify 目录总入口：检查当前服务器是否还能正常跑。
#
# 在服务器运行：
#   cd /root/autodl-tmp/sanmao-quant-llm
#   bash scripts/verify/verify_all.sh
#
# 它不负责下载模型，也不负责首次部署。
# 首次部署请用 scripts/env/setup_server_all.sh。

PROJECT_DIR="${PROJECT_DIR:-/root/autodl-tmp/sanmao-quant-llm}"
MODEL_PATH="${MODEL_PATH:-/root/autodl-tmp/models/qwen3-8b-awq}"
LLM_PYTHON="${LLM_PYTHON:-/root/autodl-tmp/llm-env/bin/python}"
HF_HOME="${HF_HOME:-/root/autodl-tmp/hf}"

cd "$PROJECT_DIR"

echo "== 1/4 Python tests =="
.venv/bin/pytest -q

echo "== 2/4 Market data check =="
.venv/bin/python scripts/verify/check_market_data.py --provider tiingo

echo "== 3/4 Qwen smoke test =="
if [[ -x "$LLM_PYTHON" && -d "$MODEL_PATH" ]]; then
  HF_HOME="$HF_HOME" "$LLM_PYTHON" scripts/verify/smoke_llm_qwen.py
else
  echo "Skip Qwen smoke test: missing $LLM_PYTHON or $MODEL_PATH" >&2
fi

echo "== 4/4 Current workflow smoke =="
bash scripts/run/run_all.sh

echo "verify_all complete."
