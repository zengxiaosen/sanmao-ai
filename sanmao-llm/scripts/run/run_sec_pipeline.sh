#!/usr/bin/env bash
set -euo pipefail

# 一键跑通当前最稳定的免费文本事件全链路：
# Tiingo 历史日线 + SEC EDGAR 免费 filings + 文本特征 + ML baseline + 回测。
#
# 用法：
#   bash scripts/run/run_sec_pipeline.sh
#
# 数据流说明：
#   1. fetch_sec_filings.py 下载 SEC filings，并保存成 CSV：
#        data/<strategy_id>/news/sec_filings.csv
#
#   2. run_baseline.py 读取配置：
#        config/sec_filings_baseline.yaml
#
#   3. config/sec_filings_baseline.yaml 里写明：
#        text_features.news_csv = data/<strategy_id>/news/sec_filings.csv
#
#   4. run_baseline.py 会读取这个 CSV，用 RuleBasedTextExtractor 生成文本事件：
#        data/<strategy_id>/features/text_events.parquet
#
#   5. run_baseline.py 再把文本事件按 date+symbol 聚合成每日文本特征：
#        data/<strategy_id>/features/daily_text_features.parquet
#
#   6. run_baseline.py 把每日文本特征 merge 到价格特征上，生成训练表：
#        data/<strategy_id>/features/training_features.parquet
#
#   7. DuckDB 里不是“共同写同一个物理表”。
#      它只是创建 view，指向上面的 parquet 文件：
#        text_events
#        daily_text_features
#        training_features
#        predictions
#
# 当前注意：
#   这个 SEC pipeline 还没有使用 Qwen extractor。
#   Qwen extractor 当前由 scripts/run/extract_news_with_llm.py 单独验证。
#   后续要做的是新增配置，让 run_baseline.py 可以直接读取 Qwen events。

PROJECT_DIR="${PROJECT_DIR:-/root/sanmao-ai/sanmao-llm}"
CONFIG_PATH="${CONFIG_PATH:-config/sec_filings_baseline.yaml}"
STRATEGY_ID="${STRATEGY_ID:-us_sec_rule_text_xgboost_v1}"
DATA_DIR="${DATA_DIR:-$PROJECT_DIR/data/$STRATEGY_ID}"
REPORT_DIR="${REPORT_DIR:-$PROJECT_DIR/reports/$STRATEGY_ID}"
RAW_NEWS_CSV="${RAW_NEWS_CSV:-$DATA_DIR/news/sec_filings.csv}"
cd "$PROJECT_DIR"
mkdir -p "$DATA_DIR/news" "$DATA_DIR/features" "$REPORT_DIR"

bash scripts/env/bootstrap_server.sh >/tmp/sanmao_bootstrap_sec_pipeline.log

# 下载 SEC 免费公告/财报 filings。
# 输出文件由 --output 指定，后续 run_baseline.py 会通过 YAML 配置读取它。
.venv/bin/python scripts/run/fetch_sec_filings.py \
  --symbols AAPL.US MSFT.US NVDA.US \
  --start-date 2021-01-01 \
  --end-date 2026-05-31 \
  --output "$RAW_NEWS_CSV"

# run_baseline.py 不知道上一行命令，它只读 config/sec_filings_baseline.yaml。
# 两者的“联动”靠同一个文件路径：
#   fetch_sec_filings.py 写 data/<strategy_id>/news/sec_filings.csv
#   sec_filings_baseline.yaml 读 data/<strategy_id>/news/sec_filings.csv
.venv/bin/python scripts/run/run_baseline.py \
  --config "$CONFIG_PATH"

echo "SEC pipeline completed."
echo "Metrics: $REPORT_DIR/metrics.json"
echo "Features: $DATA_DIR/features/"
