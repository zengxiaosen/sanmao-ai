#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LISTEN_ADDR="${SANMAO_CODEX_FALLBACK_LISTEN:-127.0.0.1:13100}"
PID_PATH="${SANMAO_CODEX_FALLBACK_PID:-${HOME}/.ssh/sanmao-codex-fallback.pid}"
HEALTH_URL="${SANMAO_CODEX_FALLBACK_HEALTH_URL:-http://${LISTEN_ADDR}/api/status}"

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
  local host port
  host="${LISTEN_ADDR%:*}"
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
    echo "[codex-fallback] already running: pid=${existing_pid}"
    echo "[codex-fallback] health check ok: ${HEALTH_URL}"
    exit 0
  fi
fi

listener_pid="$(find_listener_pid || true)"
if [ -n "${listener_pid}" ]; then
  echo "[codex-fallback] removing stale listener on ${LISTEN_ADDR}: pid=${listener_pid}"
  kill "${listener_pid}" 2>/dev/null || true
  sleep 1
fi

mkdir -p "$(dirname "${PID_PATH}")"
mkdir -p "${REPO_ROOT}/logs"

echo "[codex-fallback] building local proxy"
(
  cd "${REPO_ROOT}"
  /usr/bin/env go build -o "${REPO_ROOT}/bin/local-codex-fallback-proxy" ./cmd/local-codex-fallback-proxy
)

echo "[codex-fallback] starting on ${LISTEN_ADDR}"
nohup "${REPO_ROOT}/bin/local-codex-fallback-proxy" >"${REPO_ROOT}/logs/codex-fallback.stdout.log" 2>"${REPO_ROOT}/logs/codex-fallback.stderr.log" &
new_pid="$!"
printf '%s\n' "${new_pid}" > "${PID_PATH}"

if ! wait_for_health; then
  echo "[codex-fallback] failed health check: ${HEALTH_URL}" >&2
  exit 1
fi

echo "[codex-fallback] ready: pid=${new_pid}"
echo "[codex-fallback] health check ok: ${HEALTH_URL}"
