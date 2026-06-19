#!/usr/bin/env bash
set -euo pipefail

PID_PATH="${PID_PATH:-${HOME}/.ssh/sanmao-tunnel.pid}"
LOCAL_PORT="${LOCAL_PORT:-13000}"

is_pid_running() {
  local pid="$1"
  if [ -z "${pid}" ]; then
    return 1
  fi
  kill -0 "${pid}" 2>/dev/null
}

stopped=0

if [ -f "${PID_PATH}" ]; then
  pid="$(cat "${PID_PATH}" 2>/dev/null || true)"
  if is_pid_running "${pid}"; then
    kill "${pid}" 2>/dev/null || true
    stopped=1
  fi
  rm -f "${PID_PATH}"
fi

listener_pids="$(lsof -tiTCP:"${LOCAL_PORT}" -sTCP:LISTEN 2>/dev/null || true)"
if [ -n "${listener_pids}" ]; then
  printf '%s\n' "${listener_pids}" | xargs kill 2>/dev/null || true
  stopped=1
fi

if [ "${stopped}" -eq 1 ]; then
  echo "[tunnel] stopped"
else
  echo "[tunnel] no running listener on port ${LOCAL_PORT}"
fi
