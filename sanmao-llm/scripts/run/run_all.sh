#!/usr/bin/env bash
set -euo pipefail

# run 目录总入口：一键完成“取数据 -> LLM 抽取 -> 拼特征 -> 训练 -> 预测 -> 回测”。
#
# 用法：
#   cd /root/sanmao-ai/sanmao-llm
#   bash scripts/run/run_all.sh
#
# 说明：
#   - LLM 文本抽取走 Claude API（scripts/run/extract_news_with_llm.py），不需要 GPU。
#   - run_all.sh 只负责研究 / 回测主链路；文本事件抽取作为独立上游步骤（见下方第 3 步提示）。

PROJECT_DIR="${PROJECT_DIR:-/srv/dev/web-ui/sanmao-llm}"
QUANT_PYTHON="${QUANT_PYTHON:-$PROJECT_DIR/.venv/bin/python}"
STRATEGY_ID="${STRATEGY_ID:-us_sec_qwen_xgboost_v1}"
CONFIG_PATH="${CONFIG_PATH:-config/sec_filings_qwen.yaml}"
DATA_DIR="${DATA_DIR:-$PROJECT_DIR/data/$STRATEGY_ID}"
REPORT_DIR="${REPORT_DIR:-$PROJECT_DIR/reports/$STRATEGY_ID}"
MODEL_OUTPUT_DIR="${MODEL_OUTPUT_DIR:-$PROJECT_DIR/models/$STRATEGY_ID}"

# 当前主链路使用 SEC 免费公告/财报 filings 作为文本源。
RAW_NEWS_CSV="${RAW_NEWS_CSV:-$DATA_DIR/news/sec_filings.csv}"

# LLM 抽取后的结构化事件文件。
# run_baseline.py 会读取 config/sec_filings_qwen.yaml 中的 events_csv，也就是这个文件。
# （strategy_id 里的 "qwen" 只是历史命名，当前抽取实际由 Claude API 完成。）
LLM_EVENTS_CSV="${LLM_EVENTS_CSV:-$DATA_DIR/news/sec_filings_qwen_events.csv}"

# 调试抽取时先抽前 N 条 SEC 文本做端到端验证；全量跑设 LLM_LIMIT=0。
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

echo "== 3/5 Ensure LLM structured events =="
if [[ ! -s "$LLM_EVENTS_CSV" ]]; then
  echo "Missing LLM structured events: $LLM_EVENTS_CSV" >&2
  echo "Generate them first (needs ANTHROPIC_API_KEY, or use --rule-fallback-only), e.g.:" >&2
  echo "  $QUANT_PYTHON scripts/run/extract_news_with_llm.py --news-csv $RAW_NEWS_CSV --output $LLM_EVENTS_CSV --limit $LLM_LIMIT" >&2
  exit 1
else
  echo "LLM events already exist, reuse: $LLM_EVENTS_CSV"
  echo "Delete this file if you want to re-run the upstream extractor pipeline."
fi

echo "== 4/5 Train/predict/backtest with LLM text events =="
"$QUANT_PYTHON" scripts/run/run_baseline.py \
  --config "$CONFIG_PATH"

echo "== 5/5 Outputs =="
echo "Raw SEC text:       $RAW_NEWS_CSV"
echo "LLM events:         $LLM_EVENTS_CSV"
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
