#!/usr/bin/env bash
set -euo pipefail

# 打印 Aider 连接远端 Qwen3-Coder vLLM 的最小用法。
# 在服务器运行：
#   cd /root/autodl-tmp/sanmao-quant-llm
#   bash scripts/verify/show_aider_qwen3_coder.sh

BASE_URL="${BASE_URL:-http://127.0.0.1:8000/v1}"
MODEL_NAME="${MODEL_NAME:-qwen3-coder-30b-a3b-instruct-fp8}"
API_KEY="${API_KEY:-dummy}"

cat <<EOF
Aider + Qwen3-Coder vLLM

One-shot message example:
  aider \
    --model openai/${MODEL_NAME} \
    --openai-api-base ${BASE_URL} \
    --openai-api-key ${API_KEY} \
    --message "Summarize the purpose of this repository."

Interactive editing example:
  aider \
    --model openai/${MODEL_NAME} \
    --openai-api-base ${BASE_URL} \
    --openai-api-key ${API_KEY}

Equivalent environment variables:
  export OPENAI_API_BASE=${BASE_URL}
  export OPENAI_API_KEY=${API_KEY}
  aider --model openai/${MODEL_NAME}
EOF
