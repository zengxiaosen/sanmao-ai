---
name: gpu-llm-ops
description: Handle remote GPU local-LLM install, upgrade, replacement, proxy download, compatibility fixes, and serving/performance tuning for this repo. Use when working on Qwen/Qwen3-Coder deployment, cache paths, context/KV-cache sizing, or post-install verification on the server.
---

# gpu-llm-ops

## What this skill is for

用这个 skill 处理本仓库里所有**远端 GPU 本地 LLM 运维**任务，包括：

- 新机器初始化本地 LLM 环境
- 升级/替换/下线模型
- Hugging Face 下载与代理隧道
- `transformers` / `tokenizers` / `vllm` / 量化栈兼容问题
- Qwen / Qwen3-Coder 的服务化、上下文、KV cache、显存预算优化
- 安装后 smoke test 与开机恢复验证

## When to use it

当用户要求下面这些事情时，优先使用本 skill，而不是直接拼 ad-hoc 命令：

1. “帮我在服务器上装/升级/换一个本地模型”
2. “帮我把 Qwen3-Coder 部署起来做 coding agent”
3. “帮我查这个模型该怎么设置 context / KV cache / 显存”
4. “帮我修复 Hugging Face 下载、依赖冲突、vLLM 服务启动失败”
5. “帮我把旧小模型删掉/下线，换成新的主力模型”
6. “帮我把这次经验沉淀进项目”

## When not to use it

下面这些任务不需要本 skill：

- 普通量化研究脚本开发
- 价格特征 / 回测 / 券商适配代码修改
- 与本地 LLM 无关的项目文档更新
- 单纯调用外部 API（Claude/OpenAI 等）做代码解释

## Repo facts to assume

开始前默认遵守这些项目约束：

- 远端项目目录通常在：`/root/autodl-tmp/sanmao-quant-llm`
- 量化环境：项目根下 `.venv`
- LLM 环境：独立 `llm-env` 或独立 conda/venv
- 模型、HF cache、vLLM cache、日志都放数据盘，不放 30G 系统盘
- 历史文档中的 4090/50GB 结论仅作参考；新机器必须先重新检查显卡、磁盘、路径与依赖状态
- 当前 coding 模型路线以 **Qwen3-Coder** 为主
- 旧小模型（仓库现有 `qwen3-8b-awq` 经验）不再默认当作 coding 主力推荐

## Read these first

每次开始前，优先阅读并复用这些已有资料：

1. [docs/SERVER_DEPLOYMENT.md](../../../docs/SERVER_DEPLOYMENT.md)
2. [docs/LLM_DEPLOYMENT_NOTES.md](../../../docs/LLM_DEPLOYMENT_NOTES.md)
3. [docs/MODEL_STRATEGY.md](../../../docs/MODEL_STRATEGY.md)
4. [docs/ops/GPU_DEPLOYMENT_EVAL.md](../../../docs/ops/GPU_DEPLOYMENT_EVAL.md)
5. [scripts/README.md](../../../scripts/README.md)

原则：**先读文档，再提命令；先复用脚本，再决定要不要扩脚本。**

## Approved repo entrypoints

优先通过这些仓库入口执行，不要先绕开脚本：

- bootstrap 量化环境：
  - [scripts/env/bootstrap_server.sh](../../../scripts/env/bootstrap_server.sh)
- 新机器完整部署：
  - [scripts/env/setup_server_all.sh](../../../scripts/env/setup_server_all.sh)
- 下载/切换模型：
  - [scripts/env/download_llm_model.sh](../../../scripts/env/download_llm_model.sh)
- HF 代理隧道：
  - [scripts/env/open_hf_proxy_tunnel.sh](../../../scripts/env/open_hf_proxy_tunnel.sh)
- 最小 smoke test：
  - [scripts/verify/smoke_llm_qwen.py](../../../scripts/verify/smoke_llm_qwen.py)
- 开机后全链路验证：
  - [scripts/verify/start_server_workflow.sh](../../../scripts/verify/start_server_workflow.sh)
- 常规验证总入口：
  - [scripts/verify/verify_all.sh](../../../scripts/verify/verify_all.sh)

如果现有脚本不支持新的模型/服务方式，再修改脚本；不要只把临时命令留在聊天里。

## Choose one track

### Track A — Fresh remote GPU install

适用于：

- 新机器第一次部署
- 重新建立项目标准目录与环境

流程：

1. 确认 GPU / 数据盘 / Python 基础环境状态
2. 确认模型与 cache 目录落在数据盘
3. 需要时先启 HF 代理隧道
4. 优先复用 [scripts/env/setup_server_all.sh](../../../scripts/env/setup_server_all.sh)
5. 跑 [scripts/verify/start_server_workflow.sh](../../../scripts/verify/start_server_workflow.sh) 验证
6. 把安装结果和坑点写回文档

### Track B — Existing machine repair / upgrade / model replacement

适用于：

- 机器已经有项目环境
- 需要换模型、补依赖、修兼容问题

流程：

1. 先盘点当前机器：GPU、磁盘、已有模型、HF cache、环境变量、服务进程
2. 先跑 [scripts/env/bootstrap_server.sh](../../../scripts/env/bootstrap_server.sh) 修正基础环境
3. 通过 [scripts/env/download_llm_model.sh](../../../scripts/env/download_llm_model.sh) 或其后续扩展入口下载/切换模型
4. 如果是 Qwen3-Coder / vLLM 新路径，先把经验写到部署 notes，再把通用流程沉淀到脚本或文档
5. 跑 smoke test 与 verify 脚本
6. 若下线旧模型，记录删除路径、释放空间与回滚方案

### Track C — Proxy / Hugging Face download troubleshooting

适用于：

- HF 无法直连
- 模型下载慢、失败、缓存错位

流程：

1. 优先检查 `HF_HOME`、`HUGGINGFACE_HUB_CACHE`、`TRANSFORMERS_CACHE` 是否落在数据盘
2. 需要时使用 [scripts/env/open_hf_proxy_tunnel.sh](../../../scripts/env/open_hf_proxy_tunnel.sh)
3. 避免把 pip 依赖安装与 HF 模型下载代理逻辑混在一起
4. 成功后把代理依赖、缓存路径约定写回部署 notes

### Track D — Inference optimization / serving / coding-agent tuning

适用于：

- Qwen3-Coder 服务化
- context / KV cache / 并发 / 显存预算调优
- coding agent 体验优化

流程：

1. 先确认目标模型、权重格式、上下文需求、并发目标
2. 重新检查机器 VRAM / 磁盘 / cache 路径
3. 优先把推荐参数写进 [docs/LLM_DEPLOYMENT_NOTES.md](../../../docs/LLM_DEPLOYMENT_NOTES.md)
4. 若涉及抽取逻辑或 Qwen 推理行为，先看 [src/quant_llm/llm_extractor.py](../../../src/quant_llm/llm_extractor.py)
5. 若涉及服务层，优先沉淀成可复用的启动命令/脚本，而不是只记在对话里
6. 验证：模型能启动、上下文配置生效、smoke test 通过、关键日志无 OOM/显著错误

## Current direction for this repo

当前主线决策：

- coding 场景优先转向 **Qwen3-Coder**
- 不再默认推荐旧 `qwen3-8b-awq` 作为 coding 主力
- 如果后续删除/下线旧模型：
  1. 先确认路径和磁盘占用
  2. 再执行删除
  3. 最后把动作记录到部署日志与经验文档

## Documentation update rule

每次做完 GPU LLM 相关工作，都按下面规则沉淀：

1. **流程变化** → 更新本 skill
2. **兼容性 / 性能 / 模型经验** → 更新 [docs/LLM_DEPLOYMENT_NOTES.md](../../../docs/LLM_DEPLOYMENT_NOTES.md)
3. **某台机器上的真实变更事实** → 更新 [docs/ops/DEPLOYMENT_LOG.md](../../../docs/ops/DEPLOYMENT_LOG.md)

不要把关键经验只留在聊天记录里。

## Newly learned repo-specific经验

1. **本机代理可能会污染普通 SSH 连接**
   - 当本机代理打开后，直接 `ssh` 到远端有机会被重定向到 `127.0.0.1:7890`，表现为 `Connection reset by 127.0.0.1 port 7890`。
   - 在这种场景下，建立远端 SSH、rsync、远端状态检查时，优先使用**干净环境**执行，例如：
     - `env -i HOME="$HOME" PATH="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin" ssh ...`
   - 只有需要显式把本机代理转发给远端时，才用 `ssh -R 7890:127.0.0.1:7890 ...` 建反向隧道。

2. **Qwen3-Coder 的 vLLM 安装链条非常重**
   - 当前机器在 `vllm>=0.8.5` 路线上，会拉取大体量依赖：`torch`、`flashinfer`、`flashinfer-cubin`、`nvidia-cudnn-cu13`、`nvidia-nccl-cu13`、`triton` 等。
   - 这意味着：
     - 安装时间显著长于旧 `transformers + autoawq` 方案
     - 观察进度时不要只看 `vllm-env` 目录体积，因为 pip 可能长时间处于大包下载阶段
     - 远端数据盘空间要预留足够余量
   - 在安装完成前，不要误判为“卡死”；先看远端 `pip install` 进程是否仍在活跃。
   - 如果用户接受 **A 方案**（继续 vLLM，但把模型权重改为国内源下载），推荐做法是：
     1. 保留/完成 vLLM 依赖安装
     2. 模型权重优先改走 **ModelScope / 魔搭**
     3. 这样不会显著缩短 vLLM 安装时间，但通常能明显缩短后续大模型权重下载时间

3. **旧 `qwen3-8b-awq` 目前可以停用为 coding 主力，但还不能直接删**
   - 虽然它当前不占用 GPU，体积也只有约 5.7G，但现有多条旧脚本/验证链路仍默认引用它：
     - `scripts/env/setup_server_all.sh`
     - `scripts/run/run_all.sh`
     - `scripts/verify/smoke_llm_qwen.py`
     - `scripts/verify/start_server_workflow.sh`
     - `scripts/verify/verify_all.sh`
   - 正确顺序是：
     1. 先把 Qwen3-Coder 服务化跑通
     2. 再决定是否把旧 8B 保留为 extractor / smoke test 兼容模型
     3. 如果最终删除，必须先改默认链路，再记部署日志

## Safety checks before destructive actions

删除模型、清理 cache、覆盖环境前，必须先做这些检查：

1. 确认目标路径属于模型/cache，而不是项目源码或研究产物
2. 确认是否有当前正在运行的服务依赖该路径
3. 估算能释放多少空间
4. 如果用户明确说旧模型不用了，也要在回复中说明将删除什么路径
5. 执行后把结果记入部署日志
