#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="${REMOTE_HOST:-root@120.24.144.153}"
LOCAL_HOST="${LOCAL_HOST:-127.0.0.1}"
LOCAL_PORT="${LOCAL_PORT:-13000}"
REMOTE_TARGET_HOST="${REMOTE_TARGET_HOST:-127.0.0.1}"
REMOTE_TARGET_PORT="${REMOTE_TARGET_PORT:-3000}"
PID_PATH="${PID_PATH:-${HOME}/.ssh/sanmao-tunnel.pid}"
HEALTH_URL="${HEALTH_URL:-http://${LOCAL_HOST}:${LOCAL_PORT}/api/status}"

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
  lsof -tiTCP:"${LOCAL_PORT}" -sTCP:LISTEN 2>/dev/null | head -n 1
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
  echo "[tunnel] removing stale listener on ${LOCAL_HOST}:${LOCAL_PORT}: pid=${listener_pid}"
  kill "${listener_pid}" 2>/dev/null || true
  sleep 1
fi

echo "[tunnel] opening ${LOCAL_HOST}:${LOCAL_PORT} -> ${REMOTE_TARGET_HOST}:${REMOTE_TARGET_PORT} via ${REMOTE_HOST}"
ssh \
  -f \
  -N \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -L "${LOCAL_HOST}:${LOCAL_PORT}:${REMOTE_TARGET_HOST}:${REMOTE_TARGET_PORT}" \
  "${REMOTE_HOST}"

new_pid="$(find_listener_pid || true)"
if [ -z "${new_pid}" ]; then
  echo "[tunnel] failed: no listener found on ${LOCAL_HOST}:${LOCAL_PORT}" >&2
  exit 1
fi
printf '%s\n' "${new_pid}" > "${PID_PATH}"

if ! wait_for_health; then
  echo "[tunnel] failed health check: ${HEALTH_URL}" >&2
  exit 1
fi

echo "[tunnel] ready: pid=${new_pid}"
echo "[tunnel] health check ok: ${HEALTH_URL}"
