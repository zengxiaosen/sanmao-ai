#!/usr/bin/env bash
set -euo pipefail

PLIST_NAME="com.minwoo.sanmao-tunnel.plist"
TARGET_PLIST="${HOME}/Library/LaunchAgents/${PLIST_NAME}"

launchctl unload "${TARGET_PLIST}" >/dev/null 2>&1 || true
rm -f "${TARGET_PLIST}"

echo "[launchd] uninstalled: ${TARGET_PLIST}"
