#!/usr/bin/env bash
set -euo pipefail

# paper trading 总入口。
#
# 这是“模拟盘”，不是实盘：
#   - 不连接券商账户
#   - 不发送真实订单
#   - 只读取 latest_model 和最新特征
#   - 写 reports/<strategy_id>/paper_trading/ 下的模拟信号、模拟订单、模拟持仓

PROJECT_DIR="${PROJECT_DIR:-/root/autodl-tmp/sanmao-quant-llm}"
QUANT_PYTHON="${QUANT_PYTHON:-$PROJECT_DIR/.venv/bin/python}"
CONFIG_PATH="${CONFIG_PATH:-config/sec_filings_qwen.yaml}"
PAPER_OUTPUT_DIR="${PAPER_OUTPUT_DIR:-$PROJECT_DIR/reports/us_sec_qwen_xgboost_v1/paper_trading}"

cd "$PROJECT_DIR"

echo "== 1/2 Ensure latest research pipeline outputs =="
bash scripts/run/run_all.sh

echo "== 2/2 Run paper trading simulation =="
"$QUANT_PYTHON" scripts/run/run_paper_trading.py \
  --config "$CONFIG_PATH"

echo "== Paper trading outputs =="
echo "$PAPER_OUTPUT_DIR/paper_signals.csv"
echo "$PAPER_OUTPUT_DIR/paper_orders.csv"
echo "$PAPER_OUTPUT_DIR/paper_portfolio.csv"
echo "$PAPER_OUTPUT_DIR/paper_summary.json"
