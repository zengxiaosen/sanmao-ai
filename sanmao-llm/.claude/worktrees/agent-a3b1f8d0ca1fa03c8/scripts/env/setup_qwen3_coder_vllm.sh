#!/usr/bin/env bash
set -euo pipefail

# 为 Qwen3-Coder vLLM 服务准备独立环境、缓存目录和模型文件。
# 在服务器运行：
#   cd /root/autodl-tmp/sanmao-quant-llm
#   bash scripts/env/setup_qwen3_coder_vllm.sh
#
# 如果服务器不能直连 Hugging Face / PyPI，请先保证：
#   1. 本机代理监听在 127.0.0.1:7890
#   2. 已建立 SSH 反向隧道，把服务器 127.0.0.1:7890 转发到本机代理

PROJECT_DIR="${PROJECT_DIR:-/root/autodl-tmp/sanmao-quant-llm}"
PYTHON_BIN="${PYTHON_BIN:-/root/miniconda3/bin/python}"
VLLM_ENV="${VLLM_ENV:-/root/autodl-tmp/vllm-env}"
MODEL_ID="${MODEL_ID:-Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8}"
MODEL_ALIAS="${MODEL_ALIAS:-qwen3-coder-30b-a3b-instruct-fp8}"
MODEL_SOURCE="${MODEL_SOURCE:-modelscope}"
MODEL_DIR="${MODEL_DIR:-/root/autodl-tmp/models}"
HF_HOME="${HF_HOME:-/root/autodl-tmp/hf}"
HUGGINGFACE_HUB_CACHE="${HUGGINGFACE_HUB_CACHE:-$HF_HOME/hub}"
TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-$HF_HOME/transformers}"
VLLM_CACHE_ROOT="${VLLM_CACHE_ROOT:-/root/autodl-tmp/vllm}"
MODELSCOPE_CACHE="${MODELSCOPE_CACHE:-/root/autodl-tmp/modelscope}"
USE_PROXY="${USE_PROXY:-1}"
PROXY_URL="${PROXY_URL:-http://127.0.0.1:7890}"
ALL_PROXY_URL="${ALL_PROXY_URL:-socks5://127.0.0.1:7890}"
INSTALL_DEPS="${INSTALL_DEPS:-auto}"
DOWNLOAD_MODEL="${DOWNLOAD_MODEL:-1}"
VLLM_SPEC="${VLLM_SPEC:-vllm>=0.8.5}"

cd "$PROJECT_DIR"
mkdir -p "$MODEL_DIR" "$HF_HOME" "$HUGGINGFACE_HUB_CACHE" "$TRANSFORMERS_CACHE" "$VLLM_CACHE_ROOT" "$MODELSCOPE_CACHE"

export HF_HOME HUGGINGFACE_HUB_CACHE TRANSFORMERS_CACHE VLLM_CACHE_ROOT MODELSCOPE_CACHE

if [[ "$USE_PROXY" == "1" ]]; then
  export HTTP_PROXY="$PROXY_URL"
  export HTTPS_PROXY="$PROXY_URL"
  export ALL_PROXY="$ALL_PROXY_URL"
  export http_proxy="$PROXY_URL"
  export https_proxy="$PROXY_URL"
  export all_proxy="$ALL_PROXY_URL"
fi

if [[ ! -x "$VLLM_ENV/bin/python" ]]; then
  "$PYTHON_BIN" -m venv --system-site-packages "$VLLM_ENV"
  INSTALL_DEPS="1"
fi

if [[ "$INSTALL_DEPS" == "auto" ]]; then
  if "$VLLM_ENV/bin/python" - <<'PY' >/dev/null 2>&1
import vllm
import huggingface_hub
PY
  then
    INSTALL_DEPS="0"
  else
    INSTALL_DEPS="1"
  fi
fi

if [[ "$INSTALL_DEPS" == "1" ]]; then
  "$VLLM_ENV/bin/python" -m pip install --upgrade pip setuptools wheel
  "$VLLM_ENV/bin/pip" install "$VLLM_SPEC" "huggingface_hub>=0.30,<1.0" "modelscope>=1.24.0"
else
  echo "vLLM environment already imports correctly; skipping pip install."
fi

"$VLLM_ENV/bin/python" - <<'PY'
import huggingface_hub
import torch
try:
    import modelscope
except Exception:
    modelscope = None
import vllm
print("torch", torch.__version__, "cuda", torch.cuda.is_available())
print("vllm", vllm.__version__)
print("huggingface_hub", huggingface_hub.__version__)
print("modelscope", getattr(modelscope, "__version__", "missing"))
PY

if [[ "$DOWNLOAD_MODEL" == "1" ]]; then
  if [[ -d "$MODEL_DIR/$MODEL_ALIAS" ]]; then
    echo "Model directory already exists: $MODEL_DIR/$MODEL_ALIAS"
  else
    if [[ "$MODEL_SOURCE" == "modelscope" ]]; then
      "$VLLM_ENV/bin/python" - <<'PY'
from modelscope.hub.snapshot_download import snapshot_download

model_id = "Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8"
local_dir = "/root/autodl-tmp/models/qwen3-coder-30b-a3b-instruct-fp8"
cache_dir = "/root/autodl-tmp/modelscope"

snapshot_download(
    model_id=model_id,
    local_dir=local_dir,
    cache_dir=cache_dir,
    local_files_only=False,
)
PY
    else
      "$VLLM_ENV/bin/huggingface-cli" download "$MODEL_ID" \
        --local-dir "$MODEL_DIR/$MODEL_ALIAS" \
        --local-dir-use-symlinks False
    fi
  fi
fi

cat <<EOF
Qwen3-Coder vLLM environment ready.

vLLM env:
  $VLLM_ENV

Model path:
  $MODEL_DIR/$MODEL_ALIAS

Cache roots:
  HF_HOME=$HF_HOME
  HUGGINGFACE_HUB_CACHE=$HUGGINGFACE_HUB_CACHE
  TRANSFORMERS_CACHE=$TRANSFORMERS_CACHE
  VLLM_CACHE_ROOT=$VLLM_CACHE_ROOT
  MODELSCOPE_CACHE=$MODELSCOPE_CACHE

Model source:
  $MODEL_SOURCE

Next:
  bash scripts/env/start_qwen3_coder_vllm.sh
  bash scripts/verify/check_qwen3_coder_vllm.sh
EOF
