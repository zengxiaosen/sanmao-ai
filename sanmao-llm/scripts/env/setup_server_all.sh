#!/usr/bin/env bash
set -euo pipefail

# 一键部署服务器环境：量化 .venv + Qwen3-Coder vLLM 环境 + 模型准备。
# 在服务器运行：
#   cd /root/autodl-tmp/sanmao-quant-llm
#   bash scripts/env/setup_server_all.sh
#
# 说明：
#   - 这是当前主线的一键入口，面向 Qwen3-Coder vLLM。
#   - 旧 qwen3-8b-awq 已经退出默认安装路径，不再由这里下载。

PROJECT_DIR="${PROJECT_DIR:-/root/autodl-tmp/sanmao-quant-llm}"
MODEL_SOURCE="${MODEL_SOURCE:-modelscope}"
USE_PROXY="${USE_PROXY:-0}"

cd "$PROJECT_DIR"

echo "== 1/4 Bootstrap quant environment =="
bash scripts/env/bootstrap_server.sh

echo "== 2/4 Prepare Qwen3-Coder vLLM environment =="
MODEL_SOURCE="$MODEL_SOURCE" USE_PROXY="$USE_PROXY" bash scripts/env/setup_qwen3_coder_vllm.sh

echo "== 3/4 Start Qwen3-Coder vLLM service =="
bash scripts/env/start_qwen3_coder_vllm.sh

echo "== 4/4 Verify service and project tests =="
bash scripts/verify/check_qwen3_coder_vllm.sh
.venv/bin/pytest -q

cat <<EOF
Server setup complete.

Quant env:
  $PROJECT_DIR/.venv

vLLM env:
  /root/autodl-tmp/vllm-env

Model:
  /root/autodl-tmp/models/qwen3-coder-30b-a3b-instruct-fp8

Next:
  bash scripts/verify/start_server_workflow.sh
  bash scripts/verify/show_qwen3_coder_clients.sh
EOF
