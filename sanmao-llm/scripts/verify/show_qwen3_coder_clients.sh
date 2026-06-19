#!/usr/bin/env bash
set -euo pipefail

# 打印本地/远端 coding-agent 连接到 Qwen3-Coder vLLM 服务的示例。
# 在服务器运行：
#   cd /root/autodl-tmp/sanmao-quant-llm
#   bash scripts/verify/show_qwen3_coder_clients.sh

BASE_URL="${BASE_URL:-http://127.0.0.1:8000/v1}"
MODEL_NAME="${MODEL_NAME:-qwen3-coder-30b-a3b-instruct-fp8}"
API_KEY="${API_KEY:-dummy}"

cat <<EOF
Qwen3-Coder coding-agent client examples

Shared values:
  BASE_URL=${BASE_URL}
  MODEL_NAME=${MODEL_NAME}
  API_KEY=${API_KEY}

Python OpenAI client:
  from openai import OpenAI
  client = OpenAI(base_url="${BASE_URL}", api_key="${API_KEY}")
  resp = client.chat.completions.create(
      model="${MODEL_NAME}",
      messages=[
          {"role": "system", "content": "You are a precise coding assistant."},
          {"role": "user", "content": "Reply with exactly one line of Python that prints hello world."},
      ],
      temperature=0,
      max_tokens=64,
  )
  print(resp.choices[0].message.content)

Aider example:
  aider \
    --model openai/${MODEL_NAME} \
    --openai-api-base ${BASE_URL} \
    --openai-api-key ${API_KEY}

OpenHands / generic OpenAI-compatible agent fields:
  model=${MODEL_NAME}
  base_url=${BASE_URL}
  api_key=${API_KEY}

Curl example:
  curl ${BASE_URL}/chat/completions \
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
