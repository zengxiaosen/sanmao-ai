#!/usr/bin/env bash
set -euo pipefail

# 用远端 Qwen3-Coder vLLM 服务做最小 coding-agent smoke test。
# 在服务器运行：
#   cd /root/autodl-tmp/sanmao-quant-llm
#   bash scripts/verify/smoke_qwen3_coder_agent.sh

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
MODEL_NAME="${MODEL_NAME:-qwen3-coder-30b-a3b-instruct-fp8}"

python3 - <<PY
import json
import urllib.error
import urllib.request

host = ${HOST@Q}
port = int(${PORT@Q})
model_name = ${MODEL_NAME@Q}
base = f"http://{host}:{port}"

body = {
    "model": model_name,
    "messages": [
        {"role": "system", "content": "You are a precise coding assistant. Return only code when the user explicitly asks for code."},
        {"role": "user", "content": "Write a one-line Python program that prints hello world."},
    ],
    "temperature": 0,
    "max_tokens": 64,
}

req = urllib.request.Request(
    f"{base}/v1/chat/completions",
    data=json.dumps(body).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)

try:
    with urllib.request.urlopen(req, timeout=120) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
except urllib.error.HTTPError as exc:
    detail = exc.read().decode("utf-8", errors="replace")
    raise SystemExit(f"HTTP {exc.code}: {detail}")

content = payload["choices"][0]["message"].get("content", "")
print("content:", content)
PY
