#!/usr/bin/env bash
set -euo pipefail

# 检查 Qwen3-Coder vLLM OpenAI-compatible 服务是否可用。
# 在服务器运行：
#   cd /root/autodl-tmp/sanmao-quant-llm
#   bash scripts/verify/check_qwen3_coder_vllm.sh

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
MODEL_NAME="${MODEL_NAME:-qwen3-coder-30b-a3b-instruct-fp8}"
CHECK_MODELS="${CHECK_MODELS:-1}"

python3 - <<PY
import json
import urllib.error
import urllib.request

host = ${HOST@Q}
port = int(${PORT@Q})
model_name = ${MODEL_NAME@Q}
base = f"http://{host}:{port}"

if ${CHECK_MODELS@Q} == "1":
    req = urllib.request.Request(f"{base}/v1/models")
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    print("models:", json.dumps(payload, ensure_ascii=False))

body = {
    "model": model_name,
    "messages": [
        {"role": "system", "content": "You are a precise coding assistant."},
        {"role": "user", "content": "Reply with exactly one line of Python that prints hello world."},
    ],
    "temperature": 0,
    "max_tokens": 64,
}

data = json.dumps(body).encode("utf-8")
req = urllib.request.Request(
    f"{base}/v1/chat/completions",
    data=data,
    headers={"Content-Type": "application/json"},
)

try:
    with urllib.request.urlopen(req, timeout=120) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
except urllib.error.HTTPError as exc:
    detail = exc.read().decode("utf-8", errors="replace")
    raise SystemExit(f"HTTP {exc.code}: {detail}")

print("chat_completion:", json.dumps(payload, ensure_ascii=False))
content = payload["choices"][0]["message"].get("content", "")
print("content:", content)
PY
