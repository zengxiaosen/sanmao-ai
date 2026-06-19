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
USE_LEGACY_QWEN_EXTRACTOR="${USE_LEGACY_QWEN_EXTRACTOR:-0}"
QWEN3_CODER_HOST="${QWEN3_CODER_HOST:-127.0.0.1}"
QWEN3_CODER_PORT="${QWEN3_CODER_PORT:-8000}"
CHECK_QWEN3_CODER_VLLM="${CHECK_QWEN3_CODER_VLLM:-auto}"

cd "$PROJECT_DIR"

if [[ "$CHECK_QWEN3_CODER_VLLM" == "auto" ]]; then
  if python3 - <<PY >/dev/null 2>&1
import urllib.request
urllib.request.urlopen("http://${QWEN3_CODER_HOST}:${QWEN3_CODER_PORT}/health", timeout=5)
PY
  then
    CHECK_QWEN3_CODER_VLLM="1"
  else
    CHECK_QWEN3_CODER_VLLM="0"
  fi
fi

echo "== 1/5 Python tests =="
.venv/bin/pytest -q

echo "== 2/5 Market data check =="
.venv/bin/python scripts/verify/check_market_data.py --provider tiingo

echo "== 3/5 Qwen smoke test =="
if [[ "$USE_LEGACY_QWEN_EXTRACTOR" == "1" && -x "$LLM_PYTHON" && -d "$MODEL_PATH" ]]; then
  HF_HOME="$HF_HOME" "$LLM_PYTHON" scripts/verify/smoke_llm_qwen.py
else
  echo "Skip legacy Qwen smoke test: set USE_LEGACY_QWEN_EXTRACTOR=1 to run it." >&2
fi

echo "== 4/5 Qwen3-Coder vLLM check =="
if [[ "$CHECK_QWEN3_CODER_VLLM" == "1" ]]; then
  HOST="$QWEN3_CODER_HOST" PORT="$QWEN3_CODER_PORT" bash scripts/verify/check_qwen3_coder_vllm.sh
else
  echo "Skip Qwen3-Coder vLLM check: service not detected at http://${QWEN3_CODER_HOST}:${QWEN3_CODER_PORT}" >&2
fi

echo "== 5/5 Current workflow smoke =="
bash scripts/run/run_all.sh

echo "verify_all complete."
