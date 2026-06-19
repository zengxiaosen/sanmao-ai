#!/usr/bin/env bash
set -euo pipefail

# 打印 OpenHands 连接远端 Qwen3-Coder vLLM 的最小配置示例。
# 在服务器运行：
#   cd /root/autodl-tmp/sanmao-quant-llm
#   bash scripts/verify/show_openhands_qwen3_coder.sh

BASE_URL="${BASE_URL:-http://127.0.0.1:8000/v1}"
MODEL_NAME="${MODEL_NAME:-qwen3-coder-30b-a3b-instruct-fp8}"
API_KEY="${API_KEY:-dummy}"

cat <<EOF
OpenHands + Qwen3-Coder vLLM

config.toml example:

[llm]
model = "openai/${MODEL_NAME}"
api_key = "${API_KEY}"
base_url = "${BASE_URL}"

Notes:
- For OpenAI-compatible endpoints, keep the model name under the openai/ provider namespace.
- Use the same base_url/model/api_key values verified by scripts/verify/check_qwen3_coder_vllm.sh.
EOF
