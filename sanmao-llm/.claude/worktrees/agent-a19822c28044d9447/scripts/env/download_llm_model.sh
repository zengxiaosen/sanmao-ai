#!/usr/bin/env bash
set -euo pipefail

# 安全下载本地 LLM 的脚本。默认不下载任何模型，必须显式传入 alias。
# 在服务器运行：
#   cd /root/autodl-tmp/sanmao-quant-llm
#   bash scripts/env/download_llm_model.sh qwen3-8b-awq
#
# 如果服务器不能直连 Hugging Face：
#   1. 先在本机运行 scripts/env/open_hf_proxy_tunnel.sh。
#   2. 再在服务器运行本脚本，并保留 USE_PROXY=1 默认值。

MODEL_ALIAS="${1:-}"
MODEL_DIR="${MODEL_DIR:-/root/autodl-tmp/models}"
HF_HOME="${HF_HOME:-/root/autodl-tmp/hf}"
LLM_ENV="${LLM_ENV:-/root/autodl-tmp/llm-env}"
PYTHON_BIN="${PYTHON_BIN:-/root/miniconda3/bin/python}"
USE_PROXY="${USE_PROXY:-1}"
PROXY_URL="${PROXY_URL:-http://127.0.0.1:7890}"
ALL_PROXY_URL="${ALL_PROXY_URL:-socks5://127.0.0.1:7890}"
INSTALL_DEPS="${INSTALL_DEPS:-auto}"

case "$MODEL_ALIAS" in
  qwen3-14b-awq)
    MODEL_ID="Qwen/Qwen3-14B-AWQ"
    ;;
  qwen3-8b-awq)
    MODEL_ID="Qwen/Qwen3-8B-AWQ"
    ;;
  qwen3-32b-awq)
    MODEL_ID="Qwen/Qwen3-32B-AWQ"
    ;;
  deepseek-r1-distill-qwen-32b)
    MODEL_ID="deepseek-ai/DeepSeek-R1-Distill-Qwen-32B"
    ;;
  qwen2.5-coder-32b-awq)
    MODEL_ID="Qwen/Qwen2.5-Coder-32B-Instruct-AWQ"
    ;;
  *)
    cat <<'EOF'
Usage: bash scripts/env/download_llm_model.sh <alias>

Recommended current choice:
  qwen3-8b-awq                  first local text-extraction model
  qwen3-14b-awq                 smaller first text-extraction model

Larger / later:
  qwen3-32b-awq                 stronger 32B general text extraction
  deepseek-r1-distill-qwen-32b  reasoning/research model, not first priority
  qwen2.5-coder-32b-awq         local coding model, not first priority

This script intentionally downloads only one explicitly selected model.
EOF
    exit 2
    ;;
esac

mkdir -p "$MODEL_DIR" "$HF_HOME"
export HF_HOME

if [[ "$USE_PROXY" == "1" ]]; then
  export HTTP_PROXY="$PROXY_URL"
  export HTTPS_PROXY="$PROXY_URL"
  export ALL_PROXY="$ALL_PROXY_URL"
  export http_proxy="$PROXY_URL"
  export https_proxy="$PROXY_URL"
  export all_proxy="$ALL_PROXY_URL"
fi

AVAILABLE_GB="$(df -BG "$MODEL_DIR" | awk 'NR==2 {gsub("G","",$4); print $4}')"
if [[ "$AVAILABLE_GB" -lt 20 ]]; then
  echo "Not enough free disk under $MODEL_DIR: ${AVAILABLE_GB}GB available" >&2
  exit 1
fi

if [[ ! -x "$LLM_ENV/bin/python" ]]; then
  "$PYTHON_BIN" -m venv --system-site-packages "$LLM_ENV"
  INSTALL_DEPS="1"
fi

if [[ "$INSTALL_DEPS" == "auto" ]]; then
  if "$LLM_ENV/bin/python" - <<'PY' >/dev/null 2>&1
import torch
import transformers
import tokenizers
PY
  then
    INSTALL_DEPS="0"
  else
    INSTALL_DEPS="1"
  fi
fi

if [[ "$INSTALL_DEPS" == "1" ]]; then
  # pip 使用国内镜像即可，不需要走 Hugging Face 代理；否则本机代理慢时会拖住依赖检查。
  env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy \
    "$LLM_ENV/bin/python" -m pip install --upgrade pip setuptools wheel
  env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy \
    "$LLM_ENV/bin/pip" install \
      "transformers==4.51.3" \
      "tokenizers>=0.21,<0.22" \
      "accelerate>=1.0" \
      "huggingface_hub>=0.26,<1.0" \
      "safetensors>=0.4.5" \
      sentencepiece
else
  echo "LLM env dependencies already import correctly; skipping pip install."
fi

"$LLM_ENV/bin/python" - <<'PY'
import torch
import transformers
import tokenizers

print("torch", torch.__version__, "cuda", torch.cuda.is_available())
print("transformers", transformers.__version__)
print("tokenizers", tokenizers.__version__)
PY

echo "Downloading $MODEL_ID to $MODEL_DIR"
"$LLM_ENV/bin/huggingface-cli" download "$MODEL_ID" \
  --local-dir "$MODEL_DIR/$MODEL_ALIAS" \
  --local-dir-use-symlinks False

echo "Downloaded: $MODEL_DIR/$MODEL_ALIAS"
