#!/usr/bin/env bash
set -euo pipefail

# run 目录总入口：一键完成“取数据 -> LLM 抽取 -> 拼特征 -> 训练 -> 预测 -> 回测”。
#
# 在服务器运行：
#   cd /root/autodl-tmp/sanmao-quant-llm
#   bash scripts/run/run_all.sh
#
# 这个脚本解决的问题：
#   以前如果要用 Qwen，需要手工先跑 extract_news_with_llm.py，再跑 run_baseline.py。
#   现在不需要。run_all.sh 会自己检查 Qwen 事件文件是否存在，不存在就自动生成。

PROJECT_DIR="${PROJECT_DIR:-/root/autodl-tmp/sanmao-quant-llm}"
QUANT_PYTHON="${QUANT_PYTHON:-$PROJECT_DIR/.venv/bin/python}"
LLM_PYTHON="${LLM_PYTHON:-/root/autodl-tmp/llm-env/bin/python}"
MODEL_PATH="${MODEL_PATH:-/root/autodl-tmp/models/qwen3-8b-awq}"
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
  if [[ ! -x "$LLM_PYTHON" ]]; then
    echo "Missing LLM python: $LLM_PYTHON" >&2
    echo "Run scripts/env/setup_server_all.sh first." >&2
    exit 1
  fi
  if [[ ! -d "$MODEL_PATH" ]]; then
    echo "Missing Qwen model: $MODEL_PATH" >&2
    echo "Run scripts/env/setup_server_all.sh first." >&2
    exit 1
  fi

  echo "Qwen events not found. Extracting: $QWEN_EVENTS_CSV"
  if [[ "$LLM_LIMIT" == "0" ]]; then
    HF_HOME="$HF_HOME" "$LLM_PYTHON" scripts/run/extract_news_with_llm.py \
      --news-csv "$RAW_NEWS_CSV" \
      --output "$QWEN_EVENTS_CSV" \
      --model-path "$MODEL_PATH"
  else
    HF_HOME="$HF_HOME" "$LLM_PYTHON" scripts/run/extract_news_with_llm.py \
      --news-csv "$RAW_NEWS_CSV" \
      --output "$QWEN_EVENTS_CSV" \
      --model-path "$MODEL_PATH" \
      --limit "$LLM_LIMIT"
  fi
else
  echo "Qwen events already exist, reuse: $QWEN_EVENTS_CSV"
  echo "Delete this file if you want to re-run LLM extraction."
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
