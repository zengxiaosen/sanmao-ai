# LLM 部署经验记录

这份文档记录本项目在远端 GPU 上部署、升级、替换和优化本地 LLM 的经验，方便以后换机器、换模型或服务化时复现。

## 当前结论

当前仓库里**已经验证可运行**的旧方案是：

```text
模型：Qwen/Qwen3-8B-AWQ
模型目录：/root/autodl-tmp/models/qwen3-8b-awq
LLM 环境：/root/autodl-tmp/llm-env
PyTorch：系统 PyTorch 2.8.0+cu128
transformers：4.51.3
tokenizers：0.21.4
autoawq：0.2.9
```

但当前新的主线方向已经切到：

```text
本地 coding 模型优先转向 Qwen3-Coder
旧 qwen3-8b-awq 不再作为 coding 主力默认值
```

量化 `.venv` 和 LLM 环境分开：

| 环境 | 路径 | 用途 |
|---|---|---|
| 量化环境 | `/root/autodl-tmp/sanmao-quant-llm/.venv` | 行情、特征、ML、回测 |
| LLM 环境 | `/root/autodl-tmp/llm-env` | Qwen/transformers/autoawq/vLLM 推理 |

这样做的原因：LLM 推理依赖经常和 PyTorch/CUDA 强绑定，不能轻易污染量化研究环境。

## 当前推荐栈（准备切到 Qwen3-Coder）

对新的 96GB 单卡机器，当前推荐目标是：

```text
模型：Qwen3-Coder-30B-A3B-Instruct-FP8
用途：本地 coding agent / 代码理解 / 多文件改动 / 服务化 API
推荐默认上下文：128k
深分析模式：256k
推荐服务方向：vLLM（OpenAI-compatible API）
```

经验结论：

1. 对 coding agent，**稳定的 30B/32B 档专用 coder 模型** 比勉强塞更大的量化模型更实用。
2. 96GB Blackwell 单卡的最佳点优先是 **官方 FP8**，而不是先追 4bit。
3. 1M 上下文不适合作为当前单卡实战目标；128k/256k 更符合延迟、KV cache 和 agent 体验的平衡。

## 路径与缓存约定

无论是 transformers 直接推理还是后续 vLLM 服务化，都优先把模型和 cache 放到数据盘。

推荐环境变量：

```bash
export HF_HOME=/root/autodl-tmp/hf
export HUGGINGFACE_HUB_CACHE=/root/autodl-tmp/hf/hub
export TRANSFORMERS_CACHE=/root/autodl-tmp/hf/transformers
export VLLM_CACHE_ROOT=/root/autodl-tmp/vllm
```

经验规则：

1. 模型权重、HF cache、vLLM cache、日志都不要落到 30G 系统盘。
2. 修改模型/服务方案前，先检查当前机器的磁盘挂载与可用空间。
3. 历史 4090/50GB 数据盘经验只作参考；新机器必须重新盘点。
4. 如果本机代理打开后普通 SSH 连接被污染（例如报 `Connection reset by 127.0.0.1 port 7890`），优先用干净环境执行 SSH/rsync：

```bash
env -i HOME="$HOME" PATH="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin" ssh ...
```

只有在需要把本机代理转给远端时，才用 `ssh -R 7890:127.0.0.1:7890 ...` 建反向隧道。
5. 如果后续确认远端可以**直接访问**国内源（例如 `www.modelscope.cn:443` 能通），长时间模型下载任务优先改成**不依赖本机反向代理**，否则本地隧道断开后，远端下载进程可能保持存活但进入无进展状态。

## Qwen3-Coder 30B-A3B FP8 推荐部署参数

以下是当前面向 96GB 单卡机器的推荐目标，用于后续落地与复核：

### 仓库脚本入口

当前已经为 Qwen3-Coder vLLM 路线补齐了这几个入口：

```text
scripts/env/setup_qwen3_coder_vllm.sh
scripts/env/start_qwen3_coder_vllm.sh
scripts/verify/check_qwen3_coder_vllm.sh
```

职责：

1. `setup_qwen3_coder_vllm.sh`
   - 创建独立 `/root/autodl-tmp/vllm-env`
   - 配置 HF / transformers / vLLM cache 到数据盘
   - 安装 `vllm>=0.8.5`
   - 下载 `Qwen3-Coder-30B-A3B-Instruct-FP8`
   - 注意：这条安装链路非常重，实际会拉取 `torch`、`flashinfer`、`nvidia-cudnn-cu13`、`nvidia-nccl-cu13`、`triton` 等大依赖，耗时明显长于旧 `transformers + autoawq` 路线
   - 如果选择“继续 vLLM，但模型改走国内源下载”的 A 方案，则模型权重优先改走 **ModelScope / 魔搭**，当前已在脚本中预留 `MODEL_SOURCE=modelscope` / `MODELSCOPE_CACHE` 路径
2. `start_qwen3_coder_vllm.sh`
   - 以 OpenAI-compatible API 方式启动服务
   - 默认 `max-model-len=131072`
   - 默认 `kv-cache-dtype=fp8`
   - 默认 `gpu-memory-utilization=0.92`
   - 默认 `served-model-name=qwen3-coder-30b-a3b-instruct-fp8`
   - Blackwell 机器上额外导出：
     - `CUDA_HOME=/root/autodl-tmp/vllm-env/lib/python3.12/site-packages/nvidia/cu13`
     - `VLLM_USE_FLASHINFER_SAMPLER=0`
     - `PATH=/root/autodl-tmp/vllm-env/bin:$PATH`
   - 如果仍命中 FlashInfer / TRTLLM attention 路径异常，再进一步切换：
     - `--attention-backend FLASH_ATTN`
     - `--attention-config.use_trtllm_attention 0`
   - 如果切到 `FLASH_ATTN` 后又报 `kv_cache_dtype not supported`，说明这条路径不能继续用 `fp8` KV cache；此时要把 `kv-cache-dtype` 改回 `bfloat16`，先以可启动为目标，再回头优化显存。
   - 目的：规避 FlashInfer 在 Blackwell 上可能出现的 `FlashInfer requires GPUs with sm75 or higher` / 采样器初始化问题，以及 FlashInfer JIT 找不到 `ninja` 的问题
3. `check_qwen3_coder_vllm.sh`
   - 检查 `/v1/models`
   - 发送一个最小 chat completion 请求
   - 验证服务是否真正可用

### 日常 coding agent 模式

```text
模型：Qwen3-Coder-30B-A3B-Instruct-FP8
max-model-len：131072
kv-cache-dtype：bfloat16
attention-backend：FLASH_ATTN
attention-config.use_trtllm_attention：0
gpu-memory-utilization：0.92
max-num-seqs：8
prefix caching：开启
```

当前实测结果：

1. `/health` 返回 200
2. `/v1/models` 能看到 `qwen3-coder-30b-a3b-instruct-fp8`
3. `/v1/chat/completions` 返回 200
4. 常驻后显存占用约 89.9 GiB，剩余约 7.3 GiB
5. 通用接入字段固定为：

```text
base_url=http://127.0.0.1:8000/v1
model=qwen3-coder-30b-a3b-instruct-fp8
api_key=dummy
```

6. 适合先做一个最小 coding-agent smoke test：

```bash
bash scripts/verify/smoke_qwen3_coder_agent.sh
```

7. 如果要接实际 coding 工具，当前仓库已经提供示例入口：

```bash
bash scripts/verify/show_aider_qwen3_coder.sh
bash scripts/verify/show_openhands_qwen3_coder.sh
bash scripts/verify/show_qwen3_coder_clients.sh
```

适合：

```text
IDE/agent 改代码
大仓库检索后按需喂上下文
多轮工具调用
低延迟优先
```

### 深度项目分析模式

```text
模型：Qwen3-Coder-30B-A3B-Instruct-FP8
max-model-len：262144
kv-cache-dtype：fp8
gpu-memory-utilization：0.90
max-num-seqs：4
prefix caching：开启
```

适合：

```text
长 patch 审阅
多文件联合分析
更长文档/代码上下文
```

## Qwen3-Coder KV cache / 显存预算经验

基于当前查到的 Qwen3-Coder-30B-A3B 配置（48 layers，32 attention heads，4 KV heads，hidden_size=2048），可以先按下面经验表做容量规划：

| 上下文长度 | FP8 KV | BF16 KV |
|---|---:|---:|
| 32k | 0.75 GiB | 1.5 GiB |
| 64k | 1.5 GiB | 3 GiB |
| 128k | 3 GiB | 6 GiB |
| 256k | 6 GiB | 12 GiB |

工程判断：

1. 128k 在 96GB 单卡上是很舒服的默认点。
2. 256k 可以作为专项深分析模式。
3. 1M 即使理论可配置，也不适合作为当前单卡 coding agent 的实战目标。
4. 对 Qwen3-Coder 这档，**prefill 延迟和 agent 交互体验** 比“标称最大上下文”更重要。

经验型显存预算：

```text
模型权重 + scales + runtime 常驻：约 32~38 GiB
框架/allocator/杂项余量：约 8~12 GiB
留给 KV cache 的安全空间：约 38~48 GiB
```

## transformers 是不是有两个版本

曾经有两个版本：

1. 系统 Python 里误装过一套 `transformers 5.9.0 + tokenizers 0.23.1`。
2. `/root/autodl-tmp/llm-env` 里安装了真正用于 Qwen 的 `transformers 4.51.3 + tokenizers 0.21.4`。

系统 Python 那套后来确认没有被当前工程使用，而且版本冲突，已卸载：

```text
system transformers removed or unavailable
llm-env transformers 4.51.3
llm-env tokenizers 0.21.4
```

以后原则：

```text
不要往 /root/miniconda3 系统 Python 里装 LLM 依赖。
LLM 依赖只装进 /root/autodl-tmp/llm-env。
```

## AutoAWQ 和 transformers 版本问题

Qwen3-8B-AWQ 是 AWQ 量化模型。用 `transformers` 加载时需要 `autoawq`。

踩坑：

```text
autoawq + transformers 4.57.1 会失败
错误：cannot import name 'PytorchGELUTanh'
```

解决：

```bash
/root/autodl-tmp/llm-env/bin/pip install \
  "transformers==4.51.3" \
  "tokenizers>=0.21,<0.22" \
  autoawq
```

注意：AutoAWQ 已提示 deprecated。当前用于第一版 extractor 可以接受；长期服务化时，建议优先评估 vLLM 或其他维护更活跃的推理栈。

## Hugging Face 下载代理

服务器直连 Hugging Face 可能超时。当前做法是用本机 ClashX 代理，通过 SSH 反向端口转发给服务器。

本机运行：

```bash
cd "/Users/wumin/Documents/Obsidian Vault/论文研究/量化研究/开发部署/sanmao-quant-llm"
bash scripts/env/open_hf_proxy_tunnel.sh
```

这会建立：

```text
服务器 127.0.0.1:7890 -> 本机 127.0.0.1:7890
```

服务器下载模型时默认使用：

```text
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890
ALL_PROXY=socks5://127.0.0.1:7890
```

## 一键部署

新机器上，先同步项目代码到：

```text
/root/autodl-tmp/sanmao-quant-llm
```

如果 Hugging Face 不能直连，先在本机开代理隧道：

```bash
bash scripts/env/open_hf_proxy_tunnel.sh
```

然后服务器运行：

```bash
cd /root/autodl-tmp/sanmao-quant-llm
bash scripts/env/setup_server_all.sh
```

它会执行：

1. 创建/更新量化 `.venv`。
2. 创建/更新 `/root/autodl-tmp/llm-env`。
3. 下载默认模型。
4. 跑 Qwen JSON extraction smoke test。
5. 跑项目测试。

## 一键启动/验证

服务器关机再开机后：

```bash
cd /root/autodl-tmp/sanmao-quant-llm
bash scripts/verify/start_server_workflow.sh
```

它会执行：

1. `pytest`。
2. SEC + Tiingo baseline pipeline。
3. Qwen smoke test。
4. Qwen 样例新闻抽取。

## 旧模型淘汰规则

当前明确经验：

```text
旧 qwen3-8b-awq 不再作为 coding 主力默认模型
旧 qwen3-8b-awq 已从推荐安装路径、默认 verify 路径和远端机器默认模型目录中退出
如果仍要运行旧 extractor 兼容链路，必须显式启用 USE_LEGACY_QWEN_EXTRACTOR=1，并自行提供兼容模型路径
```

当前远端状态：

```text
/root/autodl-tmp/models/qwen3-8b-awq 已删除
/root/autodl-tmp/models/qwen3-coder-30b-a3b-instruct-fp8 为唯一保留的大模型目录
```

如果未来再恢复旧 extractor：

```text
不要默认重新下载 qwen3-8b-awq
先确认是否真的还需要那条兼容链路
```

## risk_tags 为空数组是什么意思

Qwen 输出里可能有：

```text
risk_tags=[]
```

意思是：

```text
这条文本没有抽取到明确的风险标签。
```

它不是错误。

例如：

```text
2021-01-27,AAPL.US,earnings,1.0,0.95,1-5d,[]
```

解释：

```text
event_type=earnings：这是财报事件
sentiment=1.0：文本强利好
confidence=0.95：LLM 对抽取很有把握
impact_horizon=1-5d：预计影响短期 1 到 5 个交易日
risk_tags=[]：没有明确的 margin_pressure、supply_chain 等风险标签
```

如果是：

```text
risk_tags=['supply_chain']
```

意思是文本提到了供应链相关风险。

## Qwen3 thinking 输出问题

第一次测试时，Qwen3 默认输出了 `<think>...</think>` 推理文本，没有只输出 JSON。

解决：

1. prompt 开头加入 `/no_think`。
2. `apply_chat_template(..., enable_thinking=False)`。
3. 生成时使用确定性参数：

```text
do_sample=False
temperature=None
top_p=None
top_k=None
```

正式代码位置：

```text
src/quant_llm/llm_extractor.py
```
