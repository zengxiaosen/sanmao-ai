#!/usr/bin/env bash
set -euo pipefail

BRANCH="${1:-main}"
APP_DIR="/opt/sanmao/sanmao-api"
SERVICE_NAME="sanmao-api.service"
FRONTEND_DIR="$APP_DIR/web"
LOG_DIR="$APP_DIR/logs"

echo "[deploy] app dir: $APP_DIR"
echo "[deploy] branch: $BRANCH"

cd "$APP_DIR"

echo "[deploy] syncing repository"
git fetch origin "$BRANCH"
git checkout "$BRANCH"
git reset --hard "origin/$BRANCH"

mkdir -p "$LOG_DIR"

VERSION="$(cat VERSION 2>/dev/null || true)"
if [[ -z "$VERSION" ]]; then
  VERSION="$(git rev-parse --short HEAD)"
fi

if ! command -v bun >/dev/null 2>&1; then
  echo "[deploy] bun missing, installing via npm"
  npm install -g bun
fi

export BUN_INSTALL="${BUN_INSTALL:-$HOME/.bun}"
export PATH="$BUN_INSTALL/bin:$PATH"

echo "[deploy] frontend install"
cd "$FRONTEND_DIR"
bun install --frozen-lockfile

echo "[deploy] frontend build"
export NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=8192}"
export DISABLE_ESLINT_PLUGIN=true
export VITE_REACT_APP_VERSION="$VERSION"
bun run build

echo "[deploy] backend build"
cd "$APP_DIR"
go mod download
CGO_ENABLED=1 go build -ldflags "-s -w -X 'new-api/common.Version=$VERSION'" -o new-api

echo "[deploy] restarting service"
systemctl restart "$SERVICE_NAME"
systemctl is-active --quiet "$SERVICE_NAME"

echo "[deploy] local health check"
for attempt in {1..20}; do
  if curl --fail --silent --show-error http://127.0.0.1:3000/api/status >/dev/null; then
    echo "[deploy] health check passed"
    break
  fi

  if [[ "$attempt" -eq 20 ]]; then
    echo "[deploy] health check failed after retries" >&2
    exit 1
  fi

  sleep 2
done

echo "[deploy] done"
