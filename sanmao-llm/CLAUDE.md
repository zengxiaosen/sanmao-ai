# CLAUDE.md

## Project summary

`sanmao-quant-llm` 是一个 offline-first 的量化研究工程。仓库里的 LLM 用于**文本结构化、代码辅助和可复现的离线处理**，不直接负责真实交易决策。

**LLM 调用方式：走 Claude API（Anthropic SDK），不自部署模型、不需要 GPU。** 只需要一个 `ANTHROPIC_API_KEY`（见 `.env.example`）。工程本身在本机 `/root/sanmao-ai/sanmao-llm` 运行。

先读这些文档，再动手：

1. [README.md](README.md)
2. [docs/SERVER_DEPLOYMENT.md](docs/SERVER_DEPLOYMENT.md)
3. [docs/MODEL_STRATEGY.md](docs/MODEL_STRATEGY.md)
4. [scripts/README.md](scripts/README.md)

## Script taxonomy

仓库里的可执行逻辑优先放进既有脚本分层，不要把一次性命令散落到对话里：

- `scripts/env/`：环境准备（创建 `.venv`、安装依赖）
- `scripts/run/`：正式研究/跑数/特征生成流程
- `scripts/verify/`：环境检查、smoke test

如果一个任务已经能由现有脚本完成，优先复用脚本，而不是临时重写一遍 shell 命令。

## LLM invariants

处理 LLM 相关代码时，默认遵守这些约束：

1. **API 优先，不自部署**
   - LLM 抽取统一走 Claude API（`src/quant_llm/llm_extractor.py` 里的 `AnthropicLLMExtractor`）。
   - 不要引入本地权重加载、`transformers`/`vllm`/GPU 依赖。
   - 需要处理 Anthropic 相关任务前，务必先读 `claude-api` skill（模型 ID、SDK 用法不要凭记忆）。
2. **量化环境是唯一 Python 环境**
   - 量化研究 + LLM 抽取共用项目 `.venv`；`anthropic` 只是一个普通 pip 依赖（`pip install -e '.[llm]'`）。
3. **成本与可复现**
   - 批量抽取默认用便宜的 `claude-haiku-4-5`；抽取结果落地成 CSV，下游训练/回测复用，不每次重新调 API。
   - 抽取输出 schema（`event_type/sentiment/confidence/impact_horizon/risk_tags`）保持稳定，方便换模型或换 provider。

## Current model direction

- LLM 抽取默认模型：`claude-haiku-4-5`（`extract_news_with_llm.py --model` 可换 `claude-sonnet-5` / `claude-opus-4-8`）。
- 传统 ML（XGBoost/LightGBM/scikit-learn）负责最终可回测、可验证的预测模型；LLM 只做文本→结构化特征。

## Safety and scope

- 不把真实券商凭据、API key 写入仓库。
- 不把“LLM 直接下单”当作默认方案。
- 任何破坏性操作（删除数据、覆盖模型、清空目录）前，先确认目标路径和影响范围。
