#!/usr/bin/env bash
set -euo pipefail

# 打印当前远端 Qwen3-Coder vLLM 服务的 OpenAI-compatible 接入信息。
# 在服务器运行：
#   cd /root/autodl-tmp/sanmao-quant-llm
#   bash scripts/verify/show_qwen3_coder_endpoint.sh

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
MODEL_NAME="${MODEL_NAME:-qwen3-coder-30b-a3b-instruct-fp8}"

cat <<EOF
Qwen3-Coder OpenAI-compatible endpoint

Base URL:
  http://${HOST}:${PORT}/v1

Model name:
  ${MODEL_NAME}

Quick curl:
  curl http://${HOST}:${PORT}/v1/chat/completions \
    -H 'Content-Type: application/json' \
    -d '{
      "model": "${MODEL_NAME}",
      "messages": [
        {"role": "system", "content": "You are a precise coding assistant."},
        {"role": "user", "content": "Reply with exactly one line of Python that prints hello world."}
      ],
      "temperature": 0,
      "max_tokens": 64
    }'
EOF
