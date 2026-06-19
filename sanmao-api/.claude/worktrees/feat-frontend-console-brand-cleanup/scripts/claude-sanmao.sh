#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_BASE_URL="${SANMAO_CLAUDE_BASE_URL:-http://127.0.0.1:13000}"
DEFAULT_MODELS_URL="${SANMAO_CLAUDE_MODELS_URL:-${DEFAULT_BASE_URL}/v1/models}"
STATE_DIR="${SANMAO_CLAUDE_STATE_DIR:-${HOME}/.config/sanmao-claude}"
DEFAULT_MODEL_FILE="${STATE_DIR}/default-model"
CONFIG_FILE="${STATE_DIR}/config.env"

PRINT_ENV=false
SKIP_TUNNEL=false
LIST_MODELS=false
PICK_MODEL=false
SESSION_ONLY=false
CLEAR_DEFAULT=false
SETUP_CONFIG=false
MODEL_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    models)
      LIST_MODELS=true
      shift
      ;;
    pick)
      PICK_MODEL=true
      shift
      ;;
    setup)
      SETUP_CONFIG=true
      shift
      ;;
    clear-default)
      CLEAR_DEFAULT=true
      shift
      ;;
    --print-env)
      PRINT_ENV=true
      shift
      ;;
    --skip-tunnel)
      SKIP_TUNNEL=true
      shift
      ;;
    --list-models)
      LIST_MODELS=true
      shift
      ;;
    --pick-model)
      PICK_MODEL=true
      shift
      ;;
    --session-only)
      SESSION_ONLY=true
      shift
      ;;
    --clear-default-model)
      CLEAR_DEFAULT=true
      shift
      ;;
    --setup)
      SETUP_CONFIG=true
      shift
      ;;
    --model)
      if [[ $# -lt 2 ]]; then
        echo "[claude-sanmao] --model requires a value" >&2
        exit 1
      fi
      MODEL_OVERRIDE="$2"
      shift 2
      ;;
    --)
      shift
      break
      ;;
    *)
      break
      ;;
  esac
done

CLAUDE_ARGS=("$@")
mkdir -p "${STATE_DIR}"

load_config() {
  if [[ -f "${CONFIG_FILE}" ]]; then
    # shellcheck disable=SC1090
    source "${CONFIG_FILE}"
  fi
}

save_config() {
  local token="$1"
  umask 077
  cat > "${CONFIG_FILE}" <<EOF
SANMAO_API_KEY=${token}
EOF
}

ensure_tunnel() {
  if [[ "${SKIP_TUNNEL}" != "true" ]]; then
    bash "${SCRIPT_DIR}/start-local-tunnel.sh" >/dev/null
  fi
}

load_config

if [[ -z "${SANMAO_API_KEY:-}" && -n "${ANTHROPIC_API_KEY_SM:-}" ]]; then
  SANMAO_API_KEY="${ANTHROPIC_API_KEY_SM}"
fi
if [[ -z "${SANMAO_API_KEY:-}" && -n "${ANTHROPIC_AUTH_TOKEN_SM:-}" ]]; then
  SANMAO_API_KEY="${ANTHROPIC_AUTH_TOKEN_SM}"
fi
if [[ -z "${SANMAO_API_KEY:-}" && -n "${ANTHROPIC_API_KEY:-}" ]]; then
  SANMAO_API_KEY="${ANTHROPIC_API_KEY}"
fi

if [[ "${SETUP_CONFIG}" == "true" ]]; then
  if [[ -z "${SANMAO_API_KEY:-}" ]]; then
    printf 'Enter sanmao API key: ' >&2
    read -r SANMAO_API_KEY
  fi
  if [[ -z "${SANMAO_API_KEY:-}" ]]; then
    echo "[claude-sanmao] no API key provided" >&2
    exit 1
  fi
  save_config "${SANMAO_API_KEY}"
  echo "[claude-sanmao] saved token to ${CONFIG_FILE}" >&2
  exit 0
fi

export ANTHROPIC_API_KEY="${SANMAO_API_KEY:-}"
export ANTHROPIC_BASE_URL="${DEFAULT_BASE_URL}"
unset ANTHROPIC_AUTH_TOKEN

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "[claude-sanmao] missing SANMAO_API_KEY, ANTHROPIC_API_KEY_SM, or stored config at ${CONFIG_FILE}" >&2
  exit 1
fi

fetch_models() {
  MODELS_URL="${DEFAULT_MODELS_URL}" ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" python3 - <<'PY2'
import json
import os
import urllib.request

priority = [
    'glm-5.2', 'glm-5.1', 'glm-5',
    'qwen3.7-max', 'qwen3.7-plus',
    'deepseek-v4-pro', 'deepseek-v4-flash',
    'claude-opus-4-8', 'claude-opus-4-7', 'claude-opus-4-6',
    'claude-sonnet-4-6', 'claude-sonnet-4-5-20250929', 'claude-haiku-4-5-20251001',
    'gpt-5.5', 'gpt-5.4', 'gpt-5.4-mini', 'gpt-5.3-codex-spark', 'codex-auto-review',
]
req = urllib.request.Request(
    os.environ['MODELS_URL'],
    headers={
        'x-api-key': os.environ['ANTHROPIC_API_KEY'],
        'anthropic-version': '2023-06-01',
    },
)
with urllib.request.urlopen(req, timeout=30) as response:
    payload = json.loads(response.read().decode())
ids = [item.get('id') for item in payload.get('data', []) if isinstance(item, dict) and item.get('id')]
ordered = [model for model in priority if model in ids]
remaining = sorted(model for model in ids if model not in ordered)
for model in ordered + remaining:
    print(model)
PY2
}

pick_model() {
  local current_model="$1"
  local models_text
  models_text="$(fetch_models)"
  MODELS_TEXT="${models_text}" CURRENT_MODEL="${current_model}" python3 - <<'PY2'
import os
import sys

models = [line.strip() for line in os.environ['MODELS_TEXT'].splitlines() if line.strip()]
current = os.environ.get('CURRENT_MODEL', '').strip()
if not models:
    raise SystemExit('No models available from sanmao.')

print('Available sanmao-backed Claude models:', file=sys.stderr)
for idx, model in enumerate(models, 1):
    marker = ' *' if model == current and current else '  '
    print(f'{idx:2d}.{marker} {model}', file=sys.stderr)
print('\nEnter a number or exact model name. Empty input cancels.', file=sys.stderr)
while True:
    try:
        choice = input('Model> ').strip()
    except EOFError:
        raise SystemExit(1)
    if not choice:
        raise SystemExit(1)
    if choice.isdigit():
        index = int(choice)
        if 1 <= index <= len(models):
            print(models[index - 1])
            break
        print('Invalid number, try again.', file=sys.stderr)
        continue
    if choice in models:
        print(choice)
        break
    matches = [model for model in models if choice.lower() in model.lower()]
    if len(matches) == 1:
        print(matches[0])
        break
    if matches:
        print('Ambiguous match:', ', '.join(matches), file=sys.stderr)
    else:
        print('Model not found, try again.', file=sys.stderr)
PY2
}

if [[ "${CLEAR_DEFAULT}" == "true" ]]; then
  rm -f "${DEFAULT_MODEL_FILE}"
fi

if [[ "${PRINT_ENV}" == "true" ]]; then
  ensure_tunnel
  echo "ANTHROPIC_BASE_URL=${ANTHROPIC_BASE_URL}"
  echo "ANTHROPIC_API_KEY is set"
  echo "ANTHROPIC_AUTH_TOKEN is unset"
  if [[ -f "${DEFAULT_MODEL_FILE}" ]]; then
    echo "DEFAULT_MODEL=$(cat "${DEFAULT_MODEL_FILE}")"
  else
    echo "DEFAULT_MODEL is not set"
  fi
  echo "CONFIG_FILE=${CONFIG_FILE}"
  exit 0
fi

ensure_tunnel

if [[ "${LIST_MODELS}" == "true" ]]; then
  fetch_models
  exit 0
fi

current_default=""
if [[ -f "${DEFAULT_MODEL_FILE}" ]]; then
  current_default="$(tr -d '\n' < "${DEFAULT_MODEL_FILE}")"
fi

if [[ -z "${MODEL_OVERRIDE}" && "${PICK_MODEL}" != "true" && ${#CLAUDE_ARGS[@]} -eq 0 && -z "${current_default}" ]]; then
  PICK_MODEL=true
fi

selected_model="${MODEL_OVERRIDE}"
if [[ "${PICK_MODEL}" == "true" ]]; then
  if ! selected_model="$(pick_model "${current_default}")"; then
    echo "[claude-sanmao] model selection cancelled" >&2
    exit 1
  fi
elif [[ -z "${selected_model}" && -n "${current_default}" ]]; then
  selected_model="${current_default}"
fi

if [[ -n "${selected_model}" && "${SESSION_ONLY}" != "true" ]]; then
  printf '%s
' "${selected_model}" > "${DEFAULT_MODEL_FILE}"
fi

if [[ -n "${selected_model}" ]]; then
  exec claude --model "${selected_model}" "${CLAUDE_ARGS[@]}"
fi

exec claude "${CLAUDE_ARGS[@]}"
