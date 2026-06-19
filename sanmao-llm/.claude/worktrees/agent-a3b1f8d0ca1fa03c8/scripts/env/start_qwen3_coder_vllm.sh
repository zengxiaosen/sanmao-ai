#!/usr/bin/env bash
set -euo pipefail

# 启动 Qwen3-Coder 的 vLLM OpenAI-compatible 服务。
# 在服务器运行：
#   cd /root/autodl-tmp/sanmao-quant-llm
#   bash scripts/env/start_qwen3_coder_vllm.sh

PROJECT_DIR="${PROJECT_DIR:-/root/autodl-tmp/sanmao-quant-llm}"
VLLM_ENV="${VLLM_ENV:-/root/autodl-tmp/vllm-env}"
MODEL_PATH="${MODEL_PATH:-/root/autodl-tmp/models/qwen3-coder-30b-a3b-instruct-fp8}"
HF_HOME="${HF_HOME:-/root/autodl-tmp/hf}"
HUGGINGFACE_HUB_CACHE="${HUGGINGFACE_HUB_CACHE:-$HF_HOME/hub}"
TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-$HF_HOME/transformers}"
VLLM_CACHE_ROOT="${VLLM_CACHE_ROOT:-/root/autodl-tmp/vllm}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-qwen3-coder-30b-a3b-instruct-fp8}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-131072}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.92}"
KV_CACHE_DTYPE="${KV_CACHE_DTYPE:-fp8}"
MAX_NUM_SEQS="${MAX_NUM_SEQS:-8}"
LOG_DIR="${LOG_DIR:-/root/autodl-tmp/logs}"
LOG_FILE="${LOG_FILE:-$LOG_DIR/qwen3-coder-vllm.log}"
EXTRA_ARGS="${EXTRA_ARGS:-}"

cd "$PROJECT_DIR"
mkdir -p "$LOG_DIR" "$VLLM_CACHE_ROOT" "$HF_HOME" "$HUGGINGFACE_HUB_CACHE" "$TRANSFORMERS_CACHE"

export HF_HOME HUGGINGFACE_HUB_CACHE TRANSFORMERS_CACHE VLLM_CACHE_ROOT

nohup "$VLLM_ENV/bin/vllm" serve "$MODEL_PATH" \
  --host "$HOST" \
  --port "$PORT" \
  --served-model-name "$SERVED_MODEL_NAME" \
  --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION" \
  --max-model-len "$MAX_MODEL_LEN" \
  --kv-cache-dtype "$KV_CACHE_DTYPE" \
  --enable-prefix-caching \
  --max-num-seqs "$MAX_NUM_SEQS" \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_coder \
  $EXTRA_ARGS \
  >"$LOG_FILE" 2>&1 &

cat <<EOF
Started Qwen3-Coder vLLM server.

Log file:
  $LOG_FILE

Check:
  tail -f $LOG_FILE
  bash scripts/verify/check_qwen3_coder_vllm.sh
EOF
