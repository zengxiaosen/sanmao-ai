#!/usr/bin/env bash
set -euo pipefail

# run 目录总入口：一键完成“取数据 -> LLM 抽取 -> 拼特征 -> 训练 -> 预测 -> 回测”。
#
# 在服务器运行：
#   cd /root/autodl-tmp/sanmao-quant-llm
#   bash scripts/run/run_all.sh
#
# 说明：
#   - 当前主线已经切到 Qwen3-Coder vLLM coding-agent 服务。
#   - 这个脚本不再依赖旧 qwen3-8b-awq 默认模型，也不再自动调用本地 8B 抽取链路。
#   - 现阶段 run_all.sh 只负责研究 / 回测主链路，不再试图在这里维护旧模型兼容抽取。
#   - 如果后续要把文本事件抽取升级为 API / vLLM 服务化版本，应单独增加新的抽取入口，而不是回退到旧 8B。

PROJECT_DIR="${PROJECT_DIR:-/root/autodl-tmp/sanmao-quant-llm}"
QUANT_PYTHON="${QUANT_PYTHON:-$PROJECT_DIR/.venv/bin/python}"
HF_HOME="${HF_HOME:-/root/autodl-tmp/hf}"
STRATEGY_ID="${STRATEGY_ID:-us_sec_qwen_xgboost_v1}"
CONFIG_PATH="${CONFIG_PATH:-config/sec_filings_qwen.yaml}"
DATA_DIR="${DATA_DIR:-$PROJECT_DIR/data/$STRATEGY_ID}"
REPORT_DIR="${REPORT_DIR:-$PROJECT_DIR/reports/$STRATEGY_ID}"
MODEL_OUTPUT_DIR="${MODEL_OUTPUT_DIR:-$PROJECT_DIR/models/$STRATEGY_ID}"

# 当前主链路使用 SEC 免费公告/财报 filings 作为文本源。
RAW_NEWS_CSV="${RAW_NEWS_CSV:-$DATA_DIR/news/sec_filings.csv}"

# Qwen 抽取后的结构化事件文件。
# run_baseline.py 会读取 config/sec_filings_qwen.yaml 中的 events_csv，
# 也就是这个文件。
QWEN_EVENTS_CSV="${QWEN_EVENTS_CSV:-$DATA_DIR/news/sec_filings_qwen_events.csv}"

# 为了省 GPU 时间，默认先抽取 30 条 SEC 文本做端到端验证。
# 后续要全量跑，把 LLM_LIMIT=0。
LLM_LIMIT="${LLM_LIMIT:-30}"

cd "$PROJECT_DIR"
mkdir -p "$DATA_DIR/news" "$DATA_DIR/features" "$REPORT_DIR" "$MODEL_OUTPUT_DIR"

echo "== 1/5 Ensure quant environment =="
bash scripts/env/bootstrap_server.sh >/tmp/sanmao_bootstrap_run_all.log

echo "== 2/5 Fetch SEC filings raw text =="
"$QUANT_PYTHON" scripts/run/fetch_sec_filings.py \
  --symbols AAPL.US MSFT.US NVDA.US \
  --start-date 2021-01-01 \
  --end-date 2026-05-31 \
  --output "$RAW_NEWS_CSV"

echo "== 3/5 Ensure Qwen structured events =="
if [[ ! -s "$QWEN_EVENTS_CSV" ]]; then
  echo "Missing Qwen structured events: $QWEN_EVENTS_CSV" >&2
  echo "Generate them through the maintained extractor workflow before running run_all.sh." >&2
  exit 1
else
  echo "Qwen events already exist, reuse: $QWEN_EVENTS_CSV"
  echo "Delete this file if you want to re-run the upstream extractor pipeline."
fi

echo "== 4/5 Train/predict/backtest with Qwen text events =="
"$QUANT_PYTHON" scripts/run/run_baseline.py \
  --config "$CONFIG_PATH"

echo "== 5/5 Outputs =="
echo "Raw SEC text:       $RAW_NEWS_CSV"
echo "Qwen events:        $QWEN_EVENTS_CSV"
echo "Training features:  $DATA_DIR/features/training_features.parquet"
echo "Predictions:        $REPORT_DIR/predictions.parquet"
echo "Backtest daily CSV: $REPORT_DIR/backtest_daily.csv"
echo "Latest signals:     $REPORT_DIR/latest_signals.csv"
echo "Metrics:            $REPORT_DIR/metrics.json"
echo "Model dir:          $MODEL_OUTPUT_DIR"
echo "Candidate model:    $MODEL_OUTPUT_DIR/candidate_model.joblib"
echo "Latest model:       $MODEL_OUTPUT_DIR/latest_model.joblib (only overwritten if promotion gates pass)"
echo "DuckDB:             $DATA_DIR/quant.duckdb"

echo "== Human-readable report =="
"$QUANT_PYTHON" scripts/verify/show_report.py --config "$CONFIG_PATH"
