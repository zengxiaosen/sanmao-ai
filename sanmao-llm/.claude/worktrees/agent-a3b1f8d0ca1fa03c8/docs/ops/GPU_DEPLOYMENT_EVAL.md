# 4090 48GB 金融量化 LLM 部署评估

生成日期：2026-05-30

## 机器概况

连接别名已经配置为：

```bash
ssh seeta-gpu
```

实际盘点结果：

| 项目 | 配置 |
|---|---|
| GPU | NVIDIA GeForce RTX 4090 |
| 显存 | 49140 MiB，PyTorch 可见约 47.37 GiB |
| Driver | 595.58.03 |
| CUDA | PyTorch CUDA 12.8，驱动 runtime 显示 13.2 |
| PyTorch | 2.8.0+cu128 |
| Python | 3.12.3 |
| CPU | 平台标称 25 vCPU Intel Xeon Platinum 8470Q |
| 内存 | 平台标称 92GB |
| 系统盘 | 30GB |
| 数据盘 | `/root/autodl-tmp`，50GB SSD |
| 可用 HTTP 端口 | 6006、6008 |

注意：容器内 `lscpu/free` 可能显示宿主机级资源，不应按 208 CPU / 754GiB 内存做容量规划。按平台标称 25 vCPU / 92GB 内存规划更稳。

## 核心结论

这台机器适合部署 32B 级 4bit/AWQ/GPTQ 量化模型，是金融量化研究工作站的甜点配置。

不适合部署 DeepSeek-V3 / DeepSeek-R1 原版。DeepSeek-V3/R1 原版是 671B MoE 级别模型，即使每 token active 参数较少，也不是单张 4090 48GB 的合理部署目标。

推荐策略：

1. 常驻一个 32B 级主模型。
2. 代码模型、推理模型按需切换，不长期同时常驻。
3. 高频新闻分类使用 7B/8B 小模型或离线批处理。
4. LLM 只负责结构化特征生成，不直接输出交易决策。
5. 模型、数据、项目都放在 `/root/autodl-tmp`，不要占用 30GB 系统盘。

## 推荐模型组合

| 用途 | 推荐模型 | 说明 |
|---|---|---|
| 金融新闻/公告/舆情结构化 | `Qwen3-32B-Instruct-AWQ` 或 `Qwen3-32B` 4bit | 主力模型，负责事件、主体、情绪、影响期限、风险标签抽取 |
| 复杂推理/研究助理 | `DeepSeek-R1-Distill-Qwen-32B` 4bit/AWQ/GPTQ | 适合研报式分析、链式推理、事件归因；不建议高频实时调用 |
| 写代码 | `Qwen2.5-Coder-32B-Instruct-AWQ` | 适合作为本地 coding assistant |
| 高频低延迟分类 | `Qwen3-8B` 或 `Qwen2.5-7B-Instruct` | 新闻打标、情绪粗分类、实体初筛 |
| Embedding/相似新闻检索 | `bge-m3` 或 `Qwen3-Embedding` 系列 | 配合 FAISS/Qdrant 做语义检索、去重、事件聚类 |

## 不同任务的部署建议

### 1. 新闻/舆情到特征

LLM 应输出稳定 JSON，而不是自由文本。建议 schema：

```json
{
  "tickers": ["AAPL"],
  "companies": ["Apple Inc."],
  "event_type": "earnings|guidance|lawsuit|macro|product|management|supply_chain|policy",
  "sentiment": -1.0,
  "confidence": 0.82,
  "impact_horizon": "intraday|1-5d|1-3m|long_term",
  "novelty": 0.7,
  "risk_tags": ["regulatory", "margin_pressure"],
  "summary": "..."
}
```

这些字段进入特征库后，再交给 XGBoost/LightGBM/PyTorch 模型学习，避免把 LLM 的主观判断直接当交易信号。

### 2. 量化 ML / 回测

推荐技术栈：

```text
数据处理：polars / pandas / duckdb / pyarrow
特征存储：Parquet + DuckDB
传统 ML：xgboost / lightgbm / scikit-learn
深度学习：PyTorch
回测：vectorbt / backtrader / 自研 walk-forward 回测
实验管理：MLflow 或简单 YAML + Parquet 结果目录
```

建议目录：

```text
/root/autodl-tmp/
  models/
  data/
    raw/
    features/
    parquet/
  projects/
    sanmao-quant-llm/
  logs/
```

### 3. 写代码模型

如果主要写 Python 量化代码，优先选择：

```text
Qwen2.5-Coder-32B-Instruct-AWQ
```

原因：

1. 32B 量化后适合 48GB 单卡。
2. Python、SQL、脚本生成能力较好。
3. 相比通用推理模型，更适合补全、重构、调试。

不建议和金融主模型同时常驻。需要 coding 时停掉主模型切换，或者用小模型做常驻代码助手。

## vLLM 部署建议

优先使用 vLLM 作为 OpenAI-compatible API 服务。示例：

```bash
mkdir -p /root/autodl-tmp/models /root/autodl-tmp/projects /root/autodl-tmp/logs

python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen3-32B-AWQ \
  --host 0.0.0.0 \
  --port 6008 \
  --gpu-memory-utilization 0.88 \
  --max-model-len 32768
```

如果显存压力较大，将 `--max-model-len` 降到 16384 或 8192。

端口建议：

| 端口 | 用途 |
|---|---|
| 6008 | vLLM / OpenAI-compatible API |
| 6006 | TensorBoard / Jupyter / MLflow，按阶段选择一个 |

## 磁盘约束

当前数据盘只有 50GB，这是主要短板。

32B 量化模型通常需要二三十 GB 以上。多个模型加缓存、数据和环境后会很快占满。

建议：

1. 只保留一个当前使用的 32B 模型。
2. Hugging Face cache 指向数据盘。
3. 如需同时保留金融模型、代码模型、推理模型，建议加到至少 200GB 数据盘。

推荐环境变量：

```bash
export HF_HOME=/root/autodl-tmp/hf
export TRANSFORMERS_CACHE=/root/autodl-tmp/hf/transformers
export HF_HUB_CACHE=/root/autodl-tmp/hf/hub
```

## 推荐落地架构

```text
市场数据 + 新闻/公告/社媒
        ↓
清洗、去重、实体识别
        ↓
LLM/embedding 生成结构化特征
        ↓
Parquet + DuckDB 特征库
        ↓
XGBoost / LightGBM / PyTorch
        ↓
walk-forward 回测
        ↓
模拟盘/实盘信号
```

关键原则：

1. LLM 负责理解文本和生成可控特征。
2. ML 模型负责统计学习和泛化。
3. 回测负责验证信号是否稳定。
4. 实盘前必须做时间切分、样本外验证、交易成本和滑点测试。

## 推荐优先级

第一阶段：

1. 配置 Python/conda 环境。
2. 安装 vLLM、transformers、accelerate、bitsandbytes、xgboost、lightgbm、polars、duckdb。
3. 部署一个主模型：`Qwen3-32B-Instruct-AWQ`。
4. 写新闻到 JSON 特征的批处理脚本。
5. 用 DuckDB/Parquet 落地特征。

第二阶段：

1. 加 embedding 检索和新闻去重。
2. 接入市场数据。
3. 训练 XGBoost/LightGBM baseline。
4. 做 walk-forward 回测。

第三阶段：

1. 加 `DeepSeek-R1-Distill-Qwen-32B` 做复杂推理分析。
2. 加 `Qwen2.5-Coder-32B-Instruct-AWQ` 做本地代码助手。
3. 如果磁盘不足，升级数据盘。

## 安全备注

本次已配置 SSH key 登录，后续可直接：

```bash
ssh seeta-gpu
```

由于 root 密码已经在聊天中出现，建议尽快在远端修改密码或改成只允许 SSH key 登录。

## 决策记录

### 2026-05-30：真实股票账户接入顺序

结论：当前阶段不准备、不接入真实股票账户。

原因：

1. 自动交易的主要风险不只来自模型预测错误，还包括数据复权、时区、延迟、API 重试、重复下单、网络断连、滑点、交易成本和仓位计算 bug。
2. 工程系统必须先通过离线数据、回测、模拟盘和风控验证，再进入真实账户。
3. 真实账户密钥、券商密码、交易权限属于高风险资产，不应在工程未完成时提前交给自动化系统。

推进顺序：

1. 先搭建离线量化工程：数据目录、特征库、回测框架、baseline 模型。
2. 用开源/免费数据验证 pipeline，例如 Yahoo Finance、Stooq、SEC filings、公开新闻样例。
3. 使用 LLM 生成结构化文本特征，但不直接让 LLM 输出买卖建议。
4. 通过 walk-forward 回测验证信号，纳入交易成本、滑点、最大回撤和换手率。
5. 后续再进入 paper trading / sandbox 账户。
6. 最后才考虑真实账户，并且必须配置只读或最小交易权限、单笔上限、日亏损上限、最大仓位、异常 kill switch。

当前执行方向：在 GPU 服务器上初始化 `/root/autodl-tmp/sanmao-quant-llm` 离线工程，不接入券商 API，不保存任何真实账户凭据。
