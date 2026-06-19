#!/usr/bin/env bash
set -euo pipefail

# GPU 机器关机/重启后，用这个脚本恢复 Qwen3-Coder vLLM 服务。
# 在服务器运行：
#   cd /root/autodl-tmp/sanmao-quant-llm
#   bash scripts/env/recover_qwen3_coder_after_boot.sh
#
# 说明：
#   1. 先恢复量化环境和目录。
#   2. 如果 Qwen3-Coder 服务已经健康，则不重复启动。
#   3. 如果服务未运行，则按当前 Blackwell 验证通过的参数重启。
#   4. 最后做最小健康检查。

PROJECT_DIR="${PROJECT_DIR:-/root/autodl-tmp/sanmao-quant-llm}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
HEALTH_URL="http://${HOST}:${PORT}/health"
MODELS_URL="http://${HOST}:${PORT}/v1/models"

cd "$PROJECT_DIR"

bash scripts/env/bootstrap_server.sh

if python3 - <<PY >/dev/null 2>&1
import urllib.request
urllib.request.urlopen("${HEALTH_URL}", timeout=5)
PY
then
  echo "Qwen3-Coder vLLM already healthy on ${HOST}:${PORT}"
else
  echo "Qwen3-Coder vLLM is down, starting it now..."
  ATTENTION_BACKEND="${ATTENTION_BACKEND:-FLASH_ATTN}" \
  USE_TRTLLM_ATTENTION="${USE_TRTLLM_ATTENTION:-0}" \
  KV_CACHE_DTYPE="${KV_CACHE_DTYPE:-bfloat16}" \
  bash scripts/env/start_qwen3_coder_vllm.sh
fi

for i in $(seq 1 20); do
  if python3 - <<PY >/dev/null 2>&1
import urllib.request
urllib.request.urlopen("${HEALTH_URL}", timeout=5)
PY
  then
    break
  fi
  sleep 5
done

python3 - <<PY
import urllib.request
for url in ["${HEALTH_URL}", "${MODELS_URL}"]:
    with urllib.request.urlopen(url, timeout=10) as r:
        print(url, r.status, r.read(300).decode("utf-8", errors="replace"))
PY

echo "Recovery complete."
