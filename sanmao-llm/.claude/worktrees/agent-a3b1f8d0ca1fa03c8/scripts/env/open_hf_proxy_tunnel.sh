#!/usr/bin/env bash
set -euo pipefail

# 在本机运行：把服务器的 127.0.0.1:7890 反向转发到本机代理。
# 用法：
#   bash scripts/env/open_hf_proxy_tunnel.sh
#
# 前提：
#   1. 本机 ClashX/代理监听 127.0.0.1:7890。
#   2. ssh seeta-gpu 可以直接登录。
#
# 说明：
#   - 这个命令会占住一个终端窗口，保持不退出。
#   - 另开一个终端再执行服务器上的下载命令。
#   - 如果服务器关机/重启，需要重新运行。

SSH_HOST="${SSH_HOST:-seeta-gpu}"
LOCAL_PROXY_HOST="${LOCAL_PROXY_HOST:-127.0.0.1}"
LOCAL_PROXY_PORT="${LOCAL_PROXY_PORT:-7890}"
REMOTE_PROXY_PORT="${REMOTE_PROXY_PORT:-7890}"

echo "Opening reverse proxy tunnel:"
echo "  server 127.0.0.1:${REMOTE_PROXY_PORT} -> local ${LOCAL_PROXY_HOST}:${LOCAL_PROXY_PORT}"
echo "Keep this terminal open while downloading Hugging Face models."

exec env -u ALL_PROXY -u all_proxy -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy \
  ssh -N \
    -o ServerAliveInterval=30 \
    -o ServerAliveCountMax=3 \
    -R "${REMOTE_PROXY_PORT}:${LOCAL_PROXY_HOST}:${LOCAL_PROXY_PORT}" \
    "$SSH_HOST"
