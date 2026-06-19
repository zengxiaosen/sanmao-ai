# CLAUDE.md

## Project summary

`sanmao-quant-llm` 是一个 offline-first 的量化研究工程。仓库里的本地 LLM 主要用于**文本结构化、代码辅助和可复现的离线处理**，不直接负责真实交易决策。

先读这些文档，再动手：

1. [README.md](README.md)
2. [docs/SERVER_DEPLOYMENT.md](docs/SERVER_DEPLOYMENT.md)
3. [docs/LLM_DEPLOYMENT_NOTES.md](docs/LLM_DEPLOYMENT_NOTES.md)
4. [docs/MODEL_STRATEGY.md](docs/MODEL_STRATEGY.md)
5. [scripts/README.md](scripts/README.md)

## Script taxonomy

仓库里的可执行逻辑优先放进既有脚本分层，不要把一次性命令散落到对话里：

- `scripts/env/`：环境准备、模型下载、代理、服务化前置工作
- `scripts/run/`：正式研究/跑数/特征生成流程
- `scripts/verify/`：环境检查、smoke test、开机后验证

如果一个任务已经能由现有脚本完成，优先复用脚本，而不是临时重写一遍 shell 命令。

## Local LLM invariants

处理远端 GPU 上的本地 LLM 时，默认遵守这些约束：

1. **数据盘优先**
   - 模型权重、HF cache、vLLM cache、日志都放数据盘。
   - 不要把大模型或缓存留在 30G 系统盘。
2. **量化环境与 LLM 环境隔离**
   - 量化研究环境保留为项目 `.venv`
   - LLM 推理/服务依赖放独立 `llm-env` 或独立 conda/venv
3. **先验证机器，再复用旧经验**
   - 历史文档里有一部分路径和容量是旧 4090 机器的结论。
   - 新机器任务开始前，先检查 `nvidia-smi`、磁盘挂载、Python 环境、cache 路径，再决定是否沿用旧脚本默认值。
4. **先沉淀经验，再扩大自动化**
   - 兼容性问题、上下文/KV cache 调优、代理下载经验先写进 [docs/LLM_DEPLOYMENT_NOTES.md](docs/LLM_DEPLOYMENT_NOTES.md)
   - 机器上的真实变更写进 [docs/ops/DEPLOYMENT_LOG.md](docs/ops/DEPLOYMENT_LOG.md)

## Use the project skill for GPU LLM ops

凡是下面这些任务，优先使用项目 skill **`gpu-llm-ops`**：

- 远端 GPU 上安装/升级/替换本地 LLM
- Hugging Face 下载、代理、缓存目录规划
- `transformers` / `vllm` / `tokenizers` / 量化栈兼容问题
- Qwen / Qwen3-Coder 服务化、上下文长度、KV cache、显存预算调优
- 安装后的 smoke test、开机恢复验证、模型下线/清理

这个 skill 的职责是：

- 先读仓库里已有部署文档
- 优先包装现有 `scripts/env` / `scripts/verify` 入口
- 把新的经验沉淀回文档，而不是只留在对话里

路径：

- `.claude/skills/gpu-llm-ops/SKILL.md`

## Current model direction

当前主线决策：

- 本地 **coding** 模型优先转向 **Qwen3-Coder** 路线
- 旧的小模型（仓库里现有经验主要围绕 `qwen3-8b-awq`）**不再作为 coding 主力默认值**
- 如果后续确认替换/删除旧模型，要把操作结果记录到 [docs/ops/DEPLOYMENT_LOG.md](docs/ops/DEPLOYMENT_LOG.md)

## Safety and scope

- 不把真实券商凭据、root 密码、API key 写入仓库
- 不把“LLM 直接下单”当作默认方案
- 任何破坏性远端操作（删除旧模型、清空 cache、覆盖环境）前，先确认目标路径和影响范围
