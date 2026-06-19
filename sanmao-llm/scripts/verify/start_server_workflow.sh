#!/usr/bin/env bash
set -euo pipefail

# 一键启动/验证当前研究链路。
#
# 兼容入口：保留这个文件名是因为之前文档和习惯里用过它。
# 新的 verify 总入口是：
#   scripts/verify/verify_all.sh
#
# 注意：这个脚本“不负责下载大模型”。
#   - 下载/安装完整环境：scripts/env/setup_server_all.sh
#   - 单独下载模型：scripts/env/download_llm_model.sh qwen3-8b-awq
#   - 本脚本：服务器已经部署好之后，用来检查环境、跑 baseline、跑 Qwen 小样本验证。
#
# 当前 Qwen 模型已经下载在：
#   /root/autodl-tmp/models/qwen3-8b-awq
#
# Hugging Face 缓存在：
#   /root/autodl-tmp/hf
#
# Qwen 小样本输出在：
#   data/llm_smoke_qwen/news/qwen_sample_events.csv
#
# 重要：当前 Qwen 小样本输出只是验证“本地 LLM 能抽取 JSON 特征”。
# 它还没有接入 run_sec_pipeline.sh 的主回测 baseline。
# 当前主回测 baseline 仍然使用 SEC filings + RuleBasedTextExtractor。
# 用途：
#   1. 服务器关机再开机后，确认量化和 LLM 环境还正常。
#   2. 跑 SEC 免费公告源 + Tiingo 日线 baseline。
#   3. 跑 Qwen 本地 LLM extractor 小样本验证。
#
# 在服务器运行：
#   cd /root/autodl-tmp/sanmao-quant-llm
#   bash scripts/verify/start_server_workflow.sh

PROJECT_DIR="${PROJECT_DIR:-/root/autodl-tmp/sanmao-quant-llm}"
MODEL_PATH="${MODEL_PATH:-/root/autodl-tmp/models/qwen3-8b-awq}"
LLM_PYTHON="${LLM_PYTHON:-/root/autodl-tmp/llm-env/bin/python}"
HF_HOME="${HF_HOME:-/root/autodl-tmp/hf}"
SMOKE_DATA_DIR="${SMOKE_DATA_DIR:-$PROJECT_DIR/data/llm_smoke_qwen}"
USE_LEGACY_QWEN_EXTRACTOR="${USE_LEGACY_QWEN_EXTRACTOR:-0}"
QWEN3_CODER_HOST="${QWEN3_CODER_HOST:-127.0.0.1}"
QWEN3_CODER_PORT="${QWEN3_CODER_PORT:-8000}"
CHECK_QWEN3_CODER_VLLM="${CHECK_QWEN3_CODER_VLLM:-auto}"

cd "$PROJECT_DIR"

if [[ "$CHECK_QWEN3_CODER_VLLM" == "auto" ]]; then
  if python3 - <<PY >/dev/null 2>&1
import urllib.request
urllib.request.urlopen("http://${QWEN3_CODER_HOST}:${QWEN3_CODER_PORT}/health", timeout=5)
PY
  then
    CHECK_QWEN3_CODER_VLLM="1"
  else
    CHECK_QWEN3_CODER_VLLM="0"
  fi
fi

echo "== Check quant tests =="
.venv/bin/pytest -q

echo "== Run SEC + Tiingo baseline pipeline =="
# 这里会调用 scripts/run/run_sec_pipeline.sh。
# run_sec_pipeline.sh 内部会：
#   1. 拉 SEC filings 到 data/us_sec_rule_text_xgboost_v1/news/sec_filings.csv
#   2. 调用 scripts/run/run_baseline.py --config config/sec_filings_baseline.yaml
#   3. run_baseline.py 读取 sec_filings.csv，生成文本特征，并和价格特征拼接
bash scripts/run/run_sec_pipeline.sh

if [[ "$USE_LEGACY_QWEN_EXTRACTOR" == "1" && -x "$LLM_PYTHON" && -d "$MODEL_PATH" ]]; then
  echo "== Run Qwen extractor smoke test =="
  # smoke_llm_qwen.py 只验证本地模型能不能加载、能不能输出合法 JSON。
  # 它不写入主训练特征，也不参与回测。
  HF_HOME="$HF_HOME" "$LLM_PYTHON" scripts/verify/smoke_llm_qwen.py

  echo "== Extract sample news with Qwen =="
  # 这里用 data_samples/news/sample_news.csv 跑 3 条样例新闻。
  # 输出 data/llm_smoke_qwen/news/qwen_sample_events.csv。
  # 这一步只是 LLM extractor 的小样本验证，不会自动被 run_baseline.py 读取。
  mkdir -p "$SMOKE_DATA_DIR/news"
  HF_HOME="$HF_HOME" "$LLM_PYTHON" scripts/run/extract_news_with_llm.py \
    --news-csv data_samples/news/sample_news.csv \
    --output "$SMOKE_DATA_DIR/news/qwen_sample_events.csv" \
    --model-path "$MODEL_PATH" \
    --limit 3
else
  echo "Skip legacy Qwen extractor checks: set USE_LEGACY_QWEN_EXTRACTOR=1 to run them." >&2
fi

if [[ "$CHECK_QWEN3_CODER_VLLM" == "1" ]]; then
  echo "== Check Qwen3-Coder vLLM service =="
  HOST="$QWEN3_CODER_HOST" PORT="$QWEN3_CODER_PORT" bash scripts/verify/check_qwen3_coder_vllm.sh
  echo "== Check Qwen3-Coder coding-agent smoke =="
  HOST="$QWEN3_CODER_HOST" PORT="$QWEN3_CODER_PORT" bash scripts/verify/smoke_qwen3_coder_agent.sh
else
  echo "Skip Qwen3-Coder vLLM checks: service not detected at http://${QWEN3_CODER_HOST}:${QWEN3_CODER_PORT}" >&2
fi

echo "Workflow ready."
