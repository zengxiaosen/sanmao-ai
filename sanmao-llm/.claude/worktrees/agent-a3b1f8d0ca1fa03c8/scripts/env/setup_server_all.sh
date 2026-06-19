#!/usr/bin/env bash
set -euo pipefail

# 一键部署服务器环境：量化 .venv + LLM llm-env + Qwen 模型。
# 在服务器运行：
#   cd /root/autodl-tmp/sanmao-quant-llm
#   bash scripts/env/setup_server_all.sh
#
# 如果服务器不能直连 Hugging Face，先在本机保持运行：
#   bash scripts/env/open_hf_proxy_tunnel.sh

PROJECT_DIR="${PROJECT_DIR:-/root/autodl-tmp/sanmao-quant-llm}"
MODEL_ALIAS="${MODEL_ALIAS:-qwen3-8b-awq}"

cd "$PROJECT_DIR"

echo "== 1/4 Bootstrap quant environment =="
bash scripts/env/bootstrap_server.sh

echo "== 2/4 Download/setup local LLM model =="
bash scripts/env/download_llm_model.sh "$MODEL_ALIAS"

echo "== 3/4 Verify Qwen JSON extraction =="
HF_HOME="${HF_HOME:-/root/autodl-tmp/hf}" \
  /root/autodl-tmp/llm-env/bin/python scripts/verify/smoke_llm_qwen.py

echo "== 4/4 Run project tests =="
.venv/bin/pytest -q

cat <<EOF
Server setup complete.

Quant env:
  $PROJECT_DIR/.venv

LLM env:
  /root/autodl-tmp/llm-env

Model:
  /root/autodl-tmp/models/$MODEL_ALIAS

Next:
  bash scripts/verify/start_server_workflow.sh
EOF
