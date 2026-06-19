#!/usr/bin/env bash
set -euo pipefail

PID_PATH="${SANMAO_CODEX_FALLBACK_PID:-${HOME}/.ssh/sanmao-codex-fallback.pid}"
LISTEN_ADDR="${SANMAO_CODEX_FALLBACK_LISTEN:-127.0.0.1:13100}"

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
    echo "[codex-fallback] stopped pid=${pid}"
  fi
  rm -f "${PID_PATH}"
fi

listener_pid="$(find_listener_pid || true)"
if [ -n "${listener_pid}" ]; then
  kill "${listener_pid}" 2>/dev/null || true
  echo "[codex-fallback] removed listener pid=${listener_pid}"
fi
