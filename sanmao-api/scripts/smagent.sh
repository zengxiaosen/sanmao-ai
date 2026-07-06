#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_BASE_URL="${SANMAO_CLAUDE_BASE_URL:-https://www.sanmao.fun}"
DEFAULT_MODELS_URL="${SANMAO_CLAUDE_MODELS_URL:-${DEFAULT_BASE_URL}/v1/models}"
STATE_DIR="${SANMAO_CLAUDE_STATE_DIR:-${HOME}/.config/smagent}"
DEFAULT_MODEL_FILE="${STATE_DIR}/default-model"
CONFIG_FILE="${STATE_DIR}/config.env"

PRINT_ENV=false
SKIP_TUNNEL=false
LIST_MODELS=false
PICK_MODEL=false
SESSION_ONLY=false
CLEAR_DEFAULT=false
SETUP_CONFIG=false
REMEMBER_MODEL=false
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
    --remember-model)
      REMEMBER_MODEL=true
      shift
      ;;
    --setup)
      SETUP_CONFIG=true
      shift
      ;;
    --model)
      if [[ $# -lt 2 ]]; then
        echo "[smagent] --model requires a value" >&2
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
HAS_CLAUDE_ARGS=false
if [[ ${#CLAUDE_ARGS[@]} -gt 0 ]]; then
  HAS_CLAUDE_ARGS=true
fi
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
  :
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
    echo "[smagent] no API key provided" >&2
    exit 1
  fi
  save_config "${SANMAO_API_KEY}"
  echo "[smagent] saved token to ${CONFIG_FILE}" >&2
  exit 0
fi

export ANTHROPIC_API_KEY="${SANMAO_API_KEY:-}"
export ANTHROPIC_BASE_URL="${DEFAULT_BASE_URL}"
unset ANTHROPIC_AUTH_TOKEN

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "[smagent] missing SANMAO_API_KEY, ANTHROPIC_API_KEY_SM, or stored config at ${CONFIG_FILE}" >&2
  exit 1
fi

fetch_models() {
  MODELS_URL="${DEFAULT_MODELS_URL}" ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" python3 - <<'PY2'
import json
import os
import sys
import urllib.error
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
try:
    with urllib.request.urlopen(req, timeout=30) as response:
        payload = json.loads(response.read().decode())
except urllib.error.HTTPError as exc:
    if exc.code == 401:
        print('[smagent] token unauthorized. It may be disabled/expired, or the saved SANMAO_API_KEY is stale.', file=sys.stderr)
        print('[smagent] run smagent-setup with a fresh token, then retry.', file=sys.stderr)
        raise SystemExit(1)
    print(f'[smagent] failed to fetch models: HTTP {exc.code}', file=sys.stderr)
    raise SystemExit(1)
except Exception as exc:
    print(f'[smagent] failed to fetch models: {exc}', file=sys.stderr)
    raise SystemExit(1)
ids = [item.get('id') for item in payload.get('data', []) if isinstance(item, dict) and item.get('id')]
ordered = [model for model in priority if model in ids]
remaining = sorted(model for model in ids if model not in ordered)
for model in ordered + remaining:
    print(model)
PY2
}

pick_model() {
  local current_model="$1"
  local models_text choice index selected line_no=0
  local -a models=()

  if ! models_text="$(fetch_models)"; then
    return 1
  fi
  while IFS= read -r line; do
    [[ -n "${line}" ]] || continue
    models+=("${line}")
  done <<< "${models_text}"

  if [[ ${#models[@]} -eq 0 ]]; then
    echo "[smagent] no models available from sanmao" >&2
    return 1
  fi

  echo "Available sanmao-backed gateway models:" >&2
  for model in "${models[@]}"; do
    line_no=$((line_no + 1))
    marker="  "
    if [[ -n "${current_model}" && "${model}" == "${current_model}" ]]; then
      marker=" *"
    fi
    printf '%2d.%s %s
' "${line_no}" "${marker}" "${model}" >&2
  done
  echo >&2
  echo "Enter a number or exact model name. Empty input cancels." >&2

  while true; do
    printf 'Model> ' >&2
    IFS= read -r choice || return 1
    choice="$(printf %s "$choice" | sed -e 's/^[[[:space:]]]*//' -e 's/[[:space:]]*$//')"
    if [[ -z "${choice}" ]]; then
      return 1
    fi
    if [[ "${choice}" =~ ^[0-9]+$ ]]; then
      index=$((choice - 1))
      if (( index >= 0 && index < ${#models[@]} )); then
        printf '%s
' "${models[$index]}"
        return 0
      fi
      echo "Invalid number, try again." >&2
      continue
    fi
    for model in "${models[@]}"; do
      if [[ "${model}" == "${choice}" ]]; then
        printf '%s
' "${model}"
        return 0
      fi
    done
    local -a matches=()
    for model in "${models[@]}"; do
      if [[ "$(printf %s "$model" | tr "[:upper:]" "[:lower:]")" == *"$(printf %s "$choice" | tr "[:upper:]" "[:lower:]")"* ]]; then
        matches+=("${model}")
      fi
    done
    if (( ${#matches[@]} == 1 )); then
      printf '%s
' "${matches[0]}"
      return 0
    fi
    if (( ${#matches[@]} > 1 )); then
      echo "Ambiguous match: ${matches[*]}" >&2
    else
      echo "Model not found, try again." >&2
    fi
  done
}


classify_model_family() {
  local model
  model="$(printf %s "$1" | tr "[:upper:]" "[:lower:]")"
  case "$model" in
    gpt-*|codex-*)
      printf 'codex
'
      ;;
    *)
      printf 'ccr
'
      ;;
  esac
}

ensure_codex_proxy() {
  :
}

ensure_ccr() {
  if ! command -v ccr >/dev/null 2>&1; then
    echo "[smagent] ccr is not installed or not on PATH." >&2
    echo "[smagent] install Claude Code Router first, then configure it for your sanmao-backed Claude-compatible models." >&2
    exit 1
  fi
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
    echo "[smagent] model selection cancelled" >&2
    exit 1
  fi
elif [[ -z "${selected_model}" && -n "${current_default}" ]]; then
  selected_model="${current_default}"
fi

if [[ -n "${selected_model}" ]]; then
  family="$(classify_model_family "${selected_model}")"
  echo "[smagent] launching model: ${selected_model}" >&2
  echo "[smagent] selected backend family: ${family}" >&2
  if [[ "${REMEMBER_MODEL}" == "true" && "${SESSION_ONLY}" != "true" ]]; then
    echo "[smagent] remembering model for future launches" >&2
    printf '%s
' "${selected_model}" > "${DEFAULT_MODEL_FILE}"
  else
    echo "[smagent] session-only model selection (not persisted)" >&2
  fi
  case "${family}" in
    ccr)
      ensure_ccr
      if [[ "${HAS_CLAUDE_ARGS}" == "true" ]]; then
        ANTHROPIC_MODEL="${selected_model}" exec ccr code "${CLAUDE_ARGS[@]}"
      fi
      ANTHROPIC_MODEL="${selected_model}" exec ccr code
      ;;
    codex)
      ensure_codex_proxy
      if [[ "${HAS_CLAUDE_ARGS}" == "true" ]]; then
        exec codex --model "${selected_model}" "${CLAUDE_ARGS[@]}"
      fi
      exec codex --model "${selected_model}"
      ;;
  esac
fi

if [[ "${HAS_CLAUDE_ARGS}" == "true" ]]; then
  exec claude "${CLAUDE_ARGS[@]}"
fi
exec claude
