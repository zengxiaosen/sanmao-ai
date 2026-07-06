#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODELS_URL="${SANMAO_MODELS_URL:-http://127.0.0.1:13000/v1/models}"
SANMAO_TOKEN="${SANMAO_API_KEY:-${ANTHROPIC_API_KEY:-}}"

if [[ -z "${SANMAO_TOKEN}" ]]; then
  echo "[smagent-models] missing SANMAO_API_KEY or ANTHROPIC_API_KEY" >&2
  exit 1
fi

bash "${SCRIPT_DIR}/start-local-tunnel.sh" >/dev/null

MODELS_URL="${MODELS_URL}" SANMAO_TOKEN="${SANMAO_TOKEN}" python3 - <<'PY'
import json, os, urllib.request
url = os.environ['MODELS_URL']
token = os.environ['SANMAO_TOKEN']
priority = [
    'glm-5.2', 'glm-5.1', 'glm-5',
    'qwen3.7-max', 'qwen3.7-plus',
    'deepseek-v4-pro', 'deepseek-v4-flash',
    'claude-opus-4-8', 'claude-opus-4-7', 'claude-opus-4-6',
    'claude-sonnet-4-6', 'claude-sonnet-4-5-20250929', 'claude-haiku-4-5-20251001',
    'gpt-5.5', 'gpt-5.4', 'gpt-5.4-mini', 'gpt-5.3-codex-spark', 'codex-auto-review',
]
req = urllib.request.Request(url, headers={'x-api-key': token, 'anthropic-version': '2023-06-01'})
with urllib.request.urlopen(req, timeout=30) as r:
    body = json.loads(r.read().decode())
ids = [item.get('id') for item in body.get('data', []) if isinstance(item, dict)]
available = [model for model in priority if model in ids]
remaining = sorted([model for model in ids if model not in available])
for model in available:
    print(model)
if remaining:
    print('\n# Other visible models')
    for model in remaining:
        print(model)
PY
