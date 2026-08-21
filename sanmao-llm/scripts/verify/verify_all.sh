#!/usr/bin/env bash
set -euo pipefail

# verify 目录总入口：检查当前环境是否还能正常跑。
#
# 用法：
#   cd /root/sanmao-ai/sanmao-llm
#   bash scripts/verify/verify_all.sh
#
# 它不负责首次部署。首次/重装环境请用 scripts/env/bootstrap_server.sh。

PROJECT_DIR="${PROJECT_DIR:-/srv/dev/web-ui/sanmao-llm}"

cd "$PROJECT_DIR"

echo "== 1/3 Python tests =="
.venv/bin/pytest -q

echo "== 2/3 Market data check =="
.venv/bin/python scripts/verify/check_market_data.py --provider tiingo

echo "== 3/3 Current workflow smoke =="
bash scripts/run/run_all.sh

echo "verify_all complete."
