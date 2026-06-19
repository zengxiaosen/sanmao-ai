#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="${REMOTE_HOST:-root@120.24.144.153}"
REMOTE_DIR="${REMOTE_DIR:-/opt/sanmao/sanmao-api}"
LOCAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BRANCH="${1:-main}"

echo "[sync] local dir: $LOCAL_DIR"
echo "[sync] remote host: $REMOTE_HOST"
echo "[sync] remote dir: $REMOTE_DIR"
echo "[sync] branch: $BRANCH"

ssh "$REMOTE_HOST" "mkdir -p '$REMOTE_DIR'"

echo "[sync] pushing repository contents"
rsync -az --delete \
  --exclude '.git' \
  --exclude 'node_modules' \
  --exclude 'web/node_modules' \
  --exclude 'web/build' \
  --exclude 'logs' \
  "$LOCAL_DIR"/ "$REMOTE_HOST:$REMOTE_DIR/"

echo "[sync] ensuring git checkout exists on remote"
ssh "$REMOTE_HOST" "
  set -euo pipefail
  if [ ! -d '$REMOTE_DIR/.git' ]; then
    git clone git@github.com:zengxiaosen/sanmao-api.git '$REMOTE_DIR'
  fi
  cd '$REMOTE_DIR'
  git fetch origin '$BRANCH'
  git checkout '$BRANCH'
  git reset --hard 'origin/$BRANCH'
  chmod +x scripts/deploy-on-server.sh
  bash scripts/deploy-on-server.sh '$BRANCH'
"

echo "[sync] done"
