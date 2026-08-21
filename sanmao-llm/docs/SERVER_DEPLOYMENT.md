# 部署与运行说明（Deployment）

当前工程在本机运行，不需要 GPU、不自部署模型。LLM 文本抽取走 Claude API。

## 工程路径

```bash
/root/sanmao-ai/sanmao-llm
```

## 创建 / 恢复环境

```bash
cd /root/sanmao-ai/sanmao-llm
bash scripts/env/bootstrap_server.sh
```

`bootstrap_server.sh` 会：检查/创建 `.venv`（需要 Python >= 3.10），安装依赖（含 `anthropic`），并建好 `data`、`reports`、`logs`、`models` 目录。

只想跑价格特征/回测、不跑 LLM 抽取时，可以只装核心依赖：

```bash
.venv/bin/pip install -e . pytest
```

## 配置 API key

LLM 抽取依赖 `ANTHROPIC_API_KEY`。把它放进项目根目录的 `.env`（参考 `.env.example`），或直接导出环境变量：

```bash
export ANTHROPIC_API_KEY=...
```

Anthropic SDK 会自动从环境变量读取，不要把真实 key 写进仓库。

## 运行验证

```bash
cd /root/sanmao-ai/sanmao-llm
.venv/bin/pytest -q
.venv/bin/python scripts/run/run_baseline.py --config config/baseline.yaml
```

检查真实市场数据 provider：

```bash
.venv/bin/python scripts/verify/check_market_data.py --provider yfinance
```

如果网络被 Yahoo/yfinance 阻断，这个脚本会失败或显示 `synthetic_fallback`，只能说明工程可跑，不能说明真实市场数据已经接入成功。

当前已接入 Tiingo，`.env` 中配置了 `TIINGO_API_KEY` 后推荐检查：

```bash
.venv/bin/python scripts/verify/check_market_data.py --provider tiingo
```

一键验证当前链路：

```bash
bash scripts/verify/verify_all.sh
```

它会跑：pytest → Tiingo 行情检查 → `run_all.sh` 全链路 smoke。

脚本之间如何联动、每个文件写在哪里，见 [docs/PIPELINE_DATA_FLOW.md](PIPELINE_DATA_FLOW.md)。

## LLM 文本抽取

抽取器是 `src/quant_llm/llm_extractor.py` 里的 `AnthropicLLMExtractor`，走 Claude API，默认模型 `claude-haiku-4-5`（批量抽取便宜、够用）。

用样例新闻验证：

```bash
cd /root/sanmao-ai/sanmao-llm
.venv/bin/python scripts/run/extract_news_with_llm.py \
  --news-csv data_samples/news/sample_news.csv \
  --output data/news/sample_events.csv \
  --limit 3
```

想要更强的抽取质量，加 `--model claude-sonnet-5` 或 `--model claude-opus-4-8`。
没有 key / 想跳过 API，用 `--rule-fallback-only` 只跑规则抽取器验证下游链路。

关于 API、传统 ML、风控层如何分工，见 [docs/MODEL_STRATEGY.md](MODEL_STRATEGY.md)。

## 当前不是实时交易系统

当前运行方式是 batch pipeline（批处理）：

```text
定时拉数据 -> 生成特征 -> 训练/预测 -> 输出信号和报告
```

后续如果进入 paper trading，可以先做日线收盘后运行；只有当策略确实需要分钟级或秒级响应时，才考虑实时行情消费和在线学习。

## 一键跑通当前全链路

当前最稳定的免费文本事件路径是：

```text
Tiingo 历史日线 + SEC EDGAR filings + 文本特征 + ML baseline + 回测
```

一键运行：

```bash
cd /root/sanmao-ai/sanmao-llm
bash scripts/run/run_sec_pipeline.sh
```

这不会连接券商真实交易账户，也不会下单。
