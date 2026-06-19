#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEFAULT_BASE_URL="${SANMAO_CLAUDE_BASE_URL:-http://127.0.0.1:13000}"
PRINT_ENV=false
SKIP_TUNNEL=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --print-env)
      PRINT_ENV=true
      shift
      ;;
    --skip-tunnel)
      SKIP_TUNNEL=true
      shift
      ;;
    *)
      break
      ;;
  esac
done

if [[ "${SKIP_TUNNEL}" != "true" ]]; then
  bash "${SCRIPT_DIR}/start-local-tunnel.sh"
fi

if [[ -n "${SANMAO_API_KEY:-}" ]]; then
  export ANTHROPIC_API_KEY="${SANMAO_API_KEY}"
fi
export ANTHROPIC_BASE_URL="${DEFAULT_BASE_URL}"

# Claude Code gets confused when both auth sources are present.
# For this launched process, force the sanmao/API-key route only.
unset ANTHROPIC_AUTH_TOKEN

if [[ "${PRINT_ENV}" == "true" ]]; then
  echo "ANTHROPIC_BASE_URL=${ANTHROPIC_BASE_URL}"
  if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
    echo "ANTHROPIC_API_KEY is set"
  else
    echo "ANTHROPIC_API_KEY is not set"
  fi
  echo "ANTHROPIC_AUTH_TOKEN is unset"
  exit 0
fi

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "[claude-sanmao] missing ANTHROPIC_API_KEY or SANMAO_API_KEY" >&2
  exit 1
fi

exec claude "$@"
