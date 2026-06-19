#!/usr/bin/env bash
set -euo pipefail

PLIST_NAME="com.minwoo.sanmao-tunnel.plist"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_PLIST="${SOURCE_DIR}/${PLIST_NAME}"
TARGET_DIR="${HOME}/Library/LaunchAgents"
TARGET_PLIST="${TARGET_DIR}/${PLIST_NAME}"

mkdir -p "${TARGET_DIR}"
mkdir -p "$(cd "${SOURCE_DIR}/.." && pwd)/logs"

cp "${SOURCE_PLIST}" "${TARGET_PLIST}"
launchctl unload "${TARGET_PLIST}" >/dev/null 2>&1 || true
launchctl load "${TARGET_PLIST}"
launchctl kickstart -k "gui/$(id -u)/com.minwoo.sanmao-tunnel"

echo "[launchd] installed: ${TARGET_PLIST}"
echo "[launchd] status:"
launchctl list | grep 'com.minwoo.sanmao-tunnel' || true
