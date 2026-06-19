# 服务器部署说明（Server Deployment）

## 登录服务器

已经配置了 SSH key 登录：

```bash
ssh seeta-gpu
```

## 服务器工程路径

```bash
/root/autodl-tmp/sanmao-quant-llm
```

说明：模型、环境、数据、报告都应该放在 `/root/autodl-tmp` 数据盘，不要放到 30GB 系统盘。

## 从本地同步代码到服务器

本地 GitHub 工程路径：

```bash
/Users/wumin/Documents/Obsidian Vault/论文研究/量化研究/开发部署/sanmao-quant-llm
```

推荐同步命令：

```bash
rsync -az --delete \
  --exclude .git \
  --exclude .venv \
  --exclude data \
  --exclude reports \
  "/Users/wumin/Documents/Obsidian Vault/论文研究/量化研究/开发部署/sanmao-quant-llm/" \
  seeta-gpu:/root/autodl-tmp/sanmao-quant-llm/
```

为什么要 exclude：

| 路径 | 原因 |
|---|---|
| `.git` | 服务器运行不需要本地 git 元数据 |
| `.venv` | 服务器环境独立创建 |
| `data` | 服务器生成的数据和缓存不要被本地覆盖 |
| `reports` | 服务器生成的实验结果不要被本地覆盖 |

## 创建 Python 环境

```bash
ssh seeta-gpu
cd /root/autodl-tmp/sanmao-quant-llm
bash scripts/env/bootstrap_server.sh
```

`bootstrap_server.sh` 适合服务器关机再开机后使用。它会检查 `.venv` 是否存在，安装/更新依赖，并创建 `data`、`reports`、`logs`、`models` 目录。

如果是新机器第一次完整部署，包括量化环境、LLM 环境、Qwen 模型下载和验证，使用：

```bash
cd /root/autodl-tmp/sanmao-quant-llm
bash scripts/env/setup_server_all.sh
```

如果服务器不能直连 Hugging Face，先在本机保持运行：

```bash
bash scripts/env/open_hf_proxy_tunnel.sh
```

## 运行验证

```bash
cd /root/autodl-tmp/sanmao-quant-llm
.venv/bin/pytest -q
.venv/bin/python scripts/run/run_baseline.py --config config/baseline.yaml
```

检查真实市场数据 provider：

```bash
.venv/bin/python scripts/verify/check_market_data.py --provider yfinance
```

如果服务器网络被 Yahoo/yfinance 阻断，这个脚本会失败或显示 `synthetic_fallback`。这时只能说明工程可跑，不能说明真实市场数据已经接入成功。

当前已接入 Tiingo。服务器 `.env` 中配置了 `TIINGO_API_KEY`，所以推荐检查：

```bash
.venv/bin/python scripts/verify/check_market_data.py --provider tiingo
```

如果只是刚开机想确认环境是否还正常：

```bash
cd /root/autodl-tmp/sanmao-quant-llm
bash scripts/verify/start_server_workflow.sh
```

`start_server_workflow.sh` 不是下载大模型脚本。它是“已部署服务器”的启动/验证脚本：

```text
pytest
SEC + Tiingo baseline
Qwen smoke test
Qwen 样例新闻抽取
```

脚本之间如何联动、每个文件写在哪里，见：

```text
docs/PIPELINE_DATA_FLOW.md
```

## 当前已验证结果

2026-05-30 验证：

```text
2 passed in 1.19s
baseline pipeline completed
```

生成文件：

```text
data/features/prices.parquet
data/features/price_features.parquet
data/quant.duckdb
reports/predictions.parquet
reports/metrics.json
```

## GPU 服务器信息

实测 GPU：

```text
NVIDIA GeForce RTX 4090, 49140 MiB
```

适合部署 32B 级量化 LLM。当前已经完成量化研究 baseline，并已部署第一版本地 Qwen LLM extractor。

## 本地 LLM 环境和 Hugging Face 代理

服务器系统 CUDA/PyTorch 环境是可用的：

```text
Python 3.12.3
torch 2.8.0+cu128
torch.cuda.is_available() == True
```

之前的问题不是 CUDA/PyTorch 不能用，而是系统 Python 里 `transformers/tokenizers` 版本冲突。后续不要继续污染系统 Python，也不要把完整 LLM 推理栈装进量化 `.venv`。

系统 Python 中误装的冲突版 `transformers/tokenizers` 已删除。当前只使用 `/root/autodl-tmp/llm-env` 里的 LLM 依赖。

当前约定：

| 环境 | 路径 | 用途 |
|---|---|---|
| 量化环境 | `/root/autodl-tmp/sanmao-quant-llm/.venv` | 行情、特征、ML、回测 |
| LLM 环境 | `/root/autodl-tmp/llm-env` | transformers、本地 Qwen 推理 |
| 模型目录 | `/root/autodl-tmp/models` | Hugging Face 模型文件 |
| HF 缓存 | `/root/autodl-tmp/hf` | Hugging Face cache |

服务器不能直连 Hugging Face 时，用本机 ClashX 代理：

本机开一个终端，保持不退出：

```bash
cd "/Users/wumin/Documents/Obsidian Vault/论文研究/量化研究/开发部署/sanmao-quant-llm"
bash scripts/env/open_hf_proxy_tunnel.sh
```

这个命令会建立：

```text
服务器 127.0.0.1:7890 -> 本机 127.0.0.1:7890
```

另开一个终端登录服务器下载模型：

```bash
ssh seeta-gpu
cd /root/autodl-tmp/sanmao-quant-llm
bash scripts/env/download_llm_model.sh qwen3-8b-awq
```

当前 Qwen 状态：

```text
已创建 /root/autodl-tmp/llm-env
已验证 torch 2.8.0+cu128 + CUDA 可用
已下载 Qwen/Qwen3-8B-AWQ
已安装 autoawq
已将 transformers 固定到 4.51.3，tokenizers 固定到 0.21.x，避免 AutoAWQ 兼容问题
已完成本地 Qwen JSON extraction smoke test
```

模型路径：

```text
/root/autodl-tmp/models/qwen3-8b-awq
```

LLM 环境路径：

```text
/root/autodl-tmp/llm-env
```

本地 Qwen extractor 验证命令：

```bash
cd /root/autodl-tmp/sanmao-quant-llm
HF_HOME=/root/autodl-tmp/hf \
  /root/autodl-tmp/llm-env/bin/python scripts/verify/smoke_llm_qwen.py
```

用 Qwen 抽取样例新闻：

```bash
cd /root/autodl-tmp/sanmao-quant-llm
HF_HOME=/root/autodl-tmp/hf \
  /root/autodl-tmp/llm-env/bin/python scripts/run/extract_news_with_llm.py \
  --news-csv data_samples/news/sample_news.csv \
  --output data/news/qwen_sample_events.csv \
  --model-path /root/autodl-tmp/models/qwen3-8b-awq \
  --limit 3
```

验证输出示例：

```text
saved 3 extracted events to data/news/qwen_sample_events.csv
```

详细部署经验和踩坑记录见：

```text
docs/LLM_DEPLOYMENT_NOTES.md
```

## Qwen3-Coder vLLM 服务

当前已经在新 GPU 机器上验证通过一套可用的 Qwen3-Coder vLLM 服务化组合。

### 已验证服务信息

```text
模型：qwen3-coder-30b-a3b-instruct-fp8
地址：http://127.0.0.1:8000/v1
```

### 当前保守可用参数

```text
attention-backend=FLASH_ATTN
attention-config.use_trtllm_attention=0
kv-cache-dtype=bfloat16
gpu-memory-utilization=0.92
max-model-len=131072
max-num-seqs=8
```

### 服务启动

```bash
cd /root/autodl-tmp/sanmao-quant-llm
bash scripts/env/start_qwen3_coder_vllm.sh
```

### 服务验证

```bash
cd /root/autodl-tmp/sanmao-quant-llm
bash scripts/verify/check_qwen3_coder_vllm.sh
bash scripts/verify/show_qwen3_coder_endpoint.sh
bash scripts/verify/show_qwen3_coder_clients.sh
bash scripts/verify/smoke_qwen3_coder_agent.sh
```

### OpenAI-compatible client 接入

最小 curl 示例：

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "qwen3-coder-30b-a3b-instruct-fp8",
    "messages": [
      {"role": "system", "content": "You are a precise coding assistant."},
      {"role": "user", "content": "Reply with exactly one line of Python that prints hello world."}
    ],
    "temperature": 0,
    "max_tokens": 64
  }'
```

Python OpenAI client 示例：

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8000/v1",
    api_key="dummy",
)

resp = client.chat.completions.create(
    model="qwen3-coder-30b-a3b-instruct-fp8",
    messages=[
        {"role": "system", "content": "You are a precise coding assistant."},
        {"role": "user", "content": "Reply with exactly one line of Python that prints hello world."},
    ],
    temperature=0,
    max_tokens=64,
)
print(resp.choices[0].message.content)
```

Aider 接入示例：

```bash
aider \
  --model openai/qwen3-coder-30b-a3b-instruct-fp8 \
  --openai-api-base http://127.0.0.1:8000/v1 \
  --openai-api-key dummy
```

通用 OpenAI-compatible agent（如 OpenHands / 其他 IDE agent）最少需要这三个字段：

```text
model=qwen3-coder-30b-a3b-instruct-fp8
base_url=http://127.0.0.1:8000/v1
api_key=dummy
```

OpenHands `config.toml` 示例：

```toml
[llm]
model = "openai/qwen3-coder-30b-a3b-instruct-fp8"
api_key = "dummy"
base_url = "http://127.0.0.1:8000/v1"
```

这些示例也可以直接用脚本打印：

```bash
bash scripts/verify/show_qwen3_coder_clients.sh
bash scripts/verify/show_aider_qwen3_coder.sh
bash scripts/verify/show_openhands_qwen3_coder.sh
```

另外可以直接跑一个最小 coding-agent smoke test：

```bash
bash scripts/verify/smoke_qwen3_coder_agent.sh
```

### 旧 8B 模型后续建议

当前旧模型：

```text
/root/autodl-tmp/models/qwen3-8b-awq
大小约 5.7G
```

它当前不占 GPU，但仍被这些默认链路引用：

- `scripts/env/setup_server_all.sh`
- `scripts/run/run_all.sh`
- `scripts/verify/smoke_llm_qwen.py`
- `scripts/verify/start_server_workflow.sh`
- `scripts/verify/verify_all.sh`

因此当前建议：

1. **先保留**，作为旧 extractor / smoke test 手动兼容模型
2. 默认主线已经切到 Qwen3-Coder vLLM；旧 8B 不再自动参与 verify/workflow，也不再是推荐安装路径
3. 如果你确认历史 extractor 结果或兼容 smoke 已经不再需要，就可以直接删除旧模型目录
4. 删除前先记录：路径、释放空间、是否仍有脚本依赖

如果你已经明确不再想使用旧 8B，那么当前最接近“真正退役”的状态是：

1. `download_llm_model.sh` 已不再允许把 `qwen3-8b-awq` 当作推荐/活跃下载目标
2. `setup_server_all.sh` 已明确收缩为旧 extractor 兼容入口
3. `verify_all.sh` / `start_server_workflow.sh` 已经能在检测到服务时自动带上 Qwen3-Coder 检查
4. 但 `run_all.sh` 与旧 smoke 脚本仍保留 8B 兼容默认值，因此旧模型还没有完成最终物理下线

### 已完成的默认链路并存改造

当前已经先把新的 Qwen3-Coder 服务检查接入这些 verify 工作流：

- `scripts/verify/verify_all.sh`
- `scripts/verify/start_server_workflow.sh`

行为变成：

1. 如果检测到 `http://127.0.0.1:8000/health` 可达，就自动追加：
   - `check_qwen3_coder_vllm.sh`
   - `smoke_qwen3_coder_agent.sh`
2. 默认**不再自动跑**旧 `qwen3-8b-awq` extractor 检查；只有显式设置：

```bash
USE_LEGACY_QWEN_EXTRACTOR=1
```

才会继续执行：
- `smoke_llm_qwen.py`
- `extract_news_with_llm.py` 小样本验证

也就是说，当前仓库已经从：

```text
旧 8B extractor 兼容链路 + 新 Qwen3-Coder coding-agent 服务并存
```

进一步收缩到：

```text
默认主线 = Qwen3-Coder vLLM 服务
旧 8B extractor = 手动按需兼容路径
```

下一步如果要真正删除旧模型，建议继续把 `setup_server_all.sh`、`run_all.sh` 等默认值逐步拆开，而不是直接删目录。

另外，当前已经明确区分了两条路：

1. **旧 extractor 兼容链路**
   - `scripts/verify/smoke_llm_qwen.py`
2. **新 Qwen3-Coder coding-agent 服务链路**
   - `scripts/env/setup_server_all.sh`
   - `scripts/env/setup_qwen3_coder_vllm.sh`
   - `scripts/env/start_qwen3_coder_vllm.sh`
   - `scripts/verify/check_qwen3_coder_vllm.sh`
   - `scripts/verify/show_qwen3_coder_endpoint.sh`
   - `scripts/verify/show_qwen3_coder_clients.sh`
   - `scripts/verify/smoke_qwen3_coder_agent.sh`

也就是说，当前已经完成“默认主线切换”，旧 8B 只剩手动兼容角色；`run_all.sh` 也不再默认依赖旧 8B 自动抽取。

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
cd /root/autodl-tmp/sanmao-quant-llm
bash scripts/run/run_sec_pipeline.sh
```

这不会连接券商真实交易账户，也不会下单。
