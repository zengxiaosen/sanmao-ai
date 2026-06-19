#!/usr/bin/env bash
set -euo pipefail

INSTALL_BIN_DIR="${SMCLAUDE_BIN_DIR:-${HOME}/.npm-global/bin}"
INSTALL_CONFIG_DIR="${SMCLAUDE_CONFIG_DIR:-${HOME}/.config/sanmao-claude}"
INSTALL_BIN="${INSTALL_BIN_DIR}/claude-sanmao"
INSTALL_TUNNEL_START="${INSTALL_CONFIG_DIR}/start-local-tunnel.sh"
INSTALL_TUNNEL_STOP="${INSTALL_CONFIG_DIR}/stop-local-tunnel.sh"

mkdir -p "${INSTALL_BIN_DIR}" "${INSTALL_CONFIG_DIR}"

cat > "${INSTALL_TUNNEL_START}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

LISTEN_ADDR="${SANMAO_TUNNEL_LISTEN:-127.0.0.1:13000}"
REMOTE_HOST="${SANMAO_TUNNEL_HOST:-root@120.24.144.153}"
REMOTE_TARGET="${SANMAO_TUNNEL_TARGET:-127.0.0.1:3000}"
PID_PATH="${SANMAO_TUNNEL_PID:-${HOME}/.ssh/sanmao-tunnel.pid}"
HEALTH_URL="${SANMAO_TUNNEL_HEALTH_URL:-http://${LISTEN_ADDR}/api/status}"

is_pid_running() {
  local pid="$1"
  if [ -z "${pid}" ]; then
    return 1
  fi
  kill -0 "${pid}" 2>/dev/null
}

cleanup_stale_pid() {
  if [ ! -f "${PID_PATH}" ]; then
    return 0
  fi
  local pid
  pid="$(cat "${PID_PATH}" 2>/dev/null || true)"
  if is_pid_running "${pid}"; then
    return 0
  fi
  rm -f "${PID_PATH}"
}

find_listener_pid() {
  local port
  port="${LISTEN_ADDR##*:}"
  lsof -tiTCP:"${port}" -sTCP:LISTEN 2>/dev/null | head -n 1
}

wait_for_health() {
  local attempt
  for attempt in 1 2 3 4 5; do
    if curl -fsS "${HEALTH_URL}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

cleanup_stale_pid

if [ -f "${PID_PATH}" ]; then
  existing_pid="$(cat "${PID_PATH}" 2>/dev/null || true)"
  if is_pid_running "${existing_pid}" && curl -fsS "${HEALTH_URL}" >/dev/null 2>&1; then
    echo "[tunnel] already running: pid=${existing_pid}"
    echo "[tunnel] health check ok: ${HEALTH_URL}"
    exit 0
  fi
fi

listener_pid="$(find_listener_pid || true)"
if [ -n "${listener_pid}" ]; then
  echo "[tunnel] removing stale listener on ${LISTEN_ADDR}: pid=${listener_pid}"
  kill "${listener_pid}" 2>/dev/null || true
  sleep 1
fi

mkdir -p "$(dirname "${PID_PATH}")"

echo "[tunnel] opening ${LISTEN_ADDR} -> ${REMOTE_TARGET} via ${REMOTE_HOST}"
ssh -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 \
  -N -L "${LISTEN_ADDR}:${REMOTE_TARGET}" "${REMOTE_HOST}" >/dev/null 2>&1 &
new_pid="$!"
printf '%s\n' "${new_pid}" > "${PID_PATH}"

if ! wait_for_health; then
  echo "[tunnel] failed health check: ${HEALTH_URL}" >&2
  exit 1
fi

echo "[tunnel] ready: pid=${new_pid}"
echo "[tunnel] health check ok: ${HEALTH_URL}"
EOF

cat > "${INSTALL_TUNNEL_STOP}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

PID_PATH="${SANMAO_TUNNEL_PID:-${HOME}/.ssh/sanmao-tunnel.pid}"
LISTEN_ADDR="${SANMAO_TUNNEL_LISTEN:-127.0.0.1:13000}"

is_pid_running() {
  local pid="$1"
  if [ -z "${pid}" ]; then
    return 1
  fi
  kill -0 "${pid}" 2>/dev/null
}

find_listener_pid() {
  local port
  port="${LISTEN_ADDR##*:}"
  lsof -tiTCP:"${port}" -sTCP:LISTEN 2>/dev/null | head -n 1
}

if [ -f "${PID_PATH}" ]; then
  pid="$(cat "${PID_PATH}" 2>/dev/null || true)"
  if is_pid_running "${pid}"; then
    kill "${pid}" 2>/dev/null || true
    echo "[tunnel] stopped pid=${pid}"
  fi
  rm -f "${PID_PATH}"
fi

listener_pid="$(find_listener_pid || true)"
if [ -n "${listener_pid}" ]; then
  kill "${listener_pid}" 2>/dev/null || true
  echo "[tunnel] removed listener pid=${listener_pid}"
fi
EOF

cat > "${INSTALL_BIN}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

START_TUNNEL_SCRIPT="${SANMAO_START_TUNNEL_SCRIPT:-${HOME}/.config/sanmao-claude/start-local-tunnel.sh}"
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
  cat > "${CONFIG_FILE}" <<EOF2
SANMAO_API_KEY=${token}
EOF2
}

ensure_tunnel() {
  if [[ "${SKIP_TUNNEL}" != "true" ]]; then
    if [[ ! -x "${START_TUNNEL_SCRIPT}" ]]; then
      echo "[claude-sanmao] missing executable tunnel helper at ${START_TUNNEL_SCRIPT}" >&2
      exit 1
    fi
    bash "${START_TUNNEL_SCRIPT}" >/dev/null
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
  local models_text choice index line_no=0
  local -a models=()

  models_text="$(fetch_models)"
  while IFS= read -r line; do
    [[ -n "${line}" ]] || continue
    models+=("${line}")
  done <<< "${models_text}"

  if [[ ${#models[@]} -eq 0 ]]; then
    echo "[claude-sanmao] no models available from sanmao" >&2
    return 1
  fi

  echo "Available sanmao-backed Claude models:" >&2
  for model in "${models[@]}"; do
    line_no=$((line_no + 1))
    marker="  "
    if [[ -n "${current_model}" && "${model}" == "${current_model}" ]]; then
      marker=" *"
    fi
    printf '%2d.%s %s\n' "${line_no}" "${marker}" "${model}" >&2
  done
  echo >&2
  echo "Enter a number or exact model name. Empty input cancels." >&2

  while true; do
    printf 'Model> ' >&2
    IFS= read -r choice || return 1
    choice="${choice## }"
    choice="${choice%% }"
    if [[ -z "${choice}" ]]; then
      return 1
    fi
    if [[ "${choice}" =~ ^[0-9]+$ ]]; then
      index=$((choice - 1))
      if (( index >= 0 && index < ${#models[@]} )); then
        printf '%s\n' "${models[$index]}"
        return 0
      fi
      echo "Invalid number, try again." >&2
      continue
    fi
    for model in "${models[@]}"; do
      if [[ "${model}" == "${choice}" ]]; then
        printf '%s\n' "${model}"
        return 0
      fi
    done
    local -a matches=()
    for model in "${models[@]}"; do
      if [[ "${model,,}" == *"${choice,,}"* ]]; then
        matches+=("${model}")
      fi
    done
    if (( ${#matches[@]} == 1 )); then
      printf '%s\n' "${matches[0]}"
      return 0
    fi
    if (( ${#matches[@]} > 1 )); then
      echo "Ambiguous match: ${matches[*]}" >&2
    else
      echo "Model not found, try again." >&2
    fi
  done
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
  printf '%s\n' "${selected_model}" > "${DEFAULT_MODEL_FILE}"
fi

if [[ -n "${selected_model}" ]]; then
  if [[ "${HAS_CLAUDE_ARGS}" == "true" ]]; then
    exec claude --model "${selected_model}" "${CLAUDE_ARGS[@]}"
  fi
  exec claude --model "${selected_model}"
fi

if [[ "${HAS_CLAUDE_ARGS}" == "true" ]]; then
  exec claude "${CLAUDE_ARGS[@]}"
fi
exec claude
EOF

cat > "${INSTALL_BIN_DIR}/smclaude" <<'EOF'
#!/usr/bin/env bash
if [[ $# -eq 0 ]]; then
  exec "${HOME}/.npm-global/bin/claude-sanmao" pick
fi
exec "${HOME}/.npm-global/bin/claude-sanmao" "$@"
EOF

cat > "${INSTALL_BIN_DIR}/smclaude-models" <<'EOF'
#!/usr/bin/env bash
exec "${HOME}/.npm-global/bin/claude-sanmao" models "$@"
EOF

cat > "${INSTALL_BIN_DIR}/smclaude-pick" <<'EOF'
#!/usr/bin/env bash
exec "${HOME}/.npm-global/bin/claude-sanmao" pick "$@"
EOF

cat > "${INSTALL_BIN_DIR}/smclaude-setup" <<'EOF'
#!/usr/bin/env bash
exec "${HOME}/.npm-global/bin/claude-sanmao" setup "$@"
EOF

chmod +x "${INSTALL_TUNNEL_START}" "${INSTALL_TUNNEL_STOP}" "${INSTALL_BIN}" \
  "${INSTALL_BIN_DIR}/smclaude" "${INSTALL_BIN_DIR}/smclaude-models" \
  "${INSTALL_BIN_DIR}/smclaude-pick" "${INSTALL_BIN_DIR}/smclaude-setup"

echo "[smclaude-install] installed launchers into ${INSTALL_BIN_DIR}"
echo "[smclaude-install] config dir: ${INSTALL_CONFIG_DIR}"
echo "[smclaude-install] next steps:"
echo "  1. ${INSTALL_BIN_DIR}/smclaude-setup"
echo "  2. ${INSTALL_BIN_DIR}/smclaude-models"
echo "  3. ${INSTALL_BIN_DIR}/smclaude or ${INSTALL_BIN_DIR}/smclaude-pick"
