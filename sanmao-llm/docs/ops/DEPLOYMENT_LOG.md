## 2026-06-18：准备切换本地 coding 模型路线到 Qwen3-Coder

背景：

1. 已经完成对新远端 GPU 机器的盘点：96GB Blackwell 单卡、1TB RAM、数据盘空间充足。
2. 用户明确要求在真正安装前，先把 LLM 安装/升级/优化相关经验沉淀成项目内可复用的 Claude skill。
3. 用户明确表示旧的小模型（当前仓库经验主要围绕 `qwen3-8b-awq`）不再作为后续 coding 主力默认值；如果后续确认不再使用，需要记录清理/下线动作。

本次动作：

1. 新增项目级 `CLAUDE.md`，把仓库脚本分层、本地 LLM 约束与 skill 路由写清楚。
2. 新增 `.claude/skills/gpu-llm-ops/SKILL.md`，作为远端 GPU 本地 LLM 安装、升级、替换、代理、验证、优化的统一操作手册。
3. 更新 `docs/LLM_DEPLOYMENT_NOTES.md`，补充 Qwen3-Coder 路线、cache 路径约定、context/KV cache/显存预算经验，以及旧小模型不再作为 coding 主力的规则。
4. 远端模型真正安装/删除动作尚未开始，本条记录属于**安装前准备与经验沉淀阶段**。
5. 已补齐 Qwen3-Coder vLLM 脚本入口：
   - `scripts/env/setup_qwen3_coder_vllm.sh`
   - `scripts/env/start_qwen3_coder_vllm.sh`
   - `scripts/verify/check_qwen3_coder_vllm.sh`

当前推荐目标：

```text
模型：Qwen3-Coder-30B-A3B-Instruct-FP8
默认上下文：128k
深分析模式：256k
服务方向：vLLM OpenAI-compatible API
```

待后续记录：

1. 远端实际安装的依赖版本与启动命令
2. 模型下载路径与 cache 目录
3. smoke test / 服务验证结果
4. 旧小模型是否删除、删除了哪些路径、释放了多少空间

当前阶段补充观察：

1. 当本机代理打开后，普通 SSH 连接可能被本地代理变量污染，报 `Connection reset by 127.0.0.1 port 7890`；后续需要优先用干净环境执行 SSH/rsync，只在需要远端走本机代理时再显式建 `ssh -R 7890:127.0.0.1:7890` 反向隧道。
2. Qwen3-Coder 的 `vllm>=0.8.5` 安装链路非常重，当前远端仍在拉取 `torch`、`flashinfer`、`nvidia-cudnn-cu13`、`nvidia-nccl-cu13`、`triton` 等大依赖，尚未进入模型权重下载阶段。
3. 旧 `qwen3-8b-awq` 当前未占用 GPU，体积约 5.7G，但还被多条默认脚本链路引用，因此当前只完成了删除前盘点，尚未执行删除。
4. 用户已明确选择 **A 方案**：继续 vLLM 路线，但后续模型权重优先改走 **ModelScope / 魔搭** 下载，以缩短大模型权重拉取时间；相应脚本与 skill 经验已更新。
5. 进一步观察发现：远端其实可直接访问 `www.modelscope.cn:443`。此前长时间下载卡在 `._____temp` 的一个重要原因，是模型下载仍然继承了 `HTTP_PROXY/HTTPS_PROXY/ALL_PROXY=127.0.0.1:7890`，而本地反向隧道中途断开后，远端 Python 进程没有退出，但写入字节停止增长，导致下载表面存活、实际无进展。
6. 因此后续修正策略应改为：**ModelScope 下载优先走远端直连，不依赖本机反向代理**；只有 Hugging Face 或其他外网源无法直连时，才显式保留 SSH 反向隧道。
7. 在完成 vLLM 环境与模型下载后，首次 `vllm serve` 启动失败；日志根因定位到 FlashInfer 在 Blackwell 上的采样/JIT 初始化：`RuntimeError: FlashInfer requires GPUs with sm75 or higher`。后续修正策略应在启动脚本中补充 Blackwell 兼容环境变量（例如 `CUDA_HOME=.../nvidia/cu13`、`VLLM_USE_FLASHINFER_SAMPLER=0`），再重新尝试服务启动。
8. 第一次 Blackwell 兼容修正后仍失败，因此继续升级策略：在启动参数中强制 `--attention-backend FLASH_ATTN` 与 `--attention-config.use_trtllm_attention 0`，尽量绕开 Blackwell 上的 FlashInfer/TRTLLM attention 初始化路径。
9. 进一步排查日志后发现第二个明确根因：FlashInfer JIT 在执行时找不到 `ninja`（`FileNotFoundError: [Errno 2] No such file or directory: 'ninja'`）。虽然 `ninja` 已安装在 `/root/autodl-tmp/vllm-env/bin/ninja`，但默认启动环境 PATH 未包含该目录，因此后续启动脚本需要显式导出 `PATH=/root/autodl-tmp/vllm-env/bin:$PATH` 并清空旧日志后重试。
10. 在补上 `PATH` 后，Blackwell 兼容问题继续暴露：强制 `FLASH_ATTN` 能绕开 FlashInfer 采样/JIT 路径，但又会因为 `kv_cache_dtype=fp8` 与 `FLASH_ATTN` 不兼容而失败（`ValueError: Selected backend AttentionBackendEnum.FLASH_ATTN is not valid for this configuration. Reason: ['kv_cache_dtype not supported']`）。后续应尝试把 `kv-cache-dtype` 从 `fp8` 回退到 `bfloat16`，优先验证服务可启动。
11. 前台验证表明：当参数组合改为 `attention-backend=FLASH_ATTN`、`use_trtllm_attention=0`、`kv-cache-dtype=bfloat16` 后，Qwen3-Coder vLLM 服务已经能够在本机成功启动并监听 `http://127.0.0.1:8000`。这说明当前真正可用的保守 Blackwell 兼容组合已经确定。
12. 后续正式后台启动也已成功：`/health` 返回 200，`/v1/models` 返回已注册模型 `qwen3-coder-30b-a3b-instruct-fp8`，`/v1/chat/completions` 也返回 200。当前服务常驻进程为 `vllm serve` + `VLLM::EngineCore`，显存占用约 89.9 GiB，剩余约 7.3 GiB。
13. 为了让旧链路和新链路先并存，已经把 `scripts/verify/verify_all.sh` 和 `scripts/verify/start_server_workflow.sh` 改成：如果检测到 `http://127.0.0.1:8000/health` 可达，就自动追加 Qwen3-Coder vLLM 检查与最小 coding-agent smoke test，同时保留旧 `qwen3-8b-awq` extractor 检查。
14. 继续收尾时，已经把 `setup_server_all.sh`、`run_all.sh`、`smoke_llm_qwen.py` 的注释和职责边界改清楚：旧 `qwen3-8b-awq` 保留为 extractor / smoke 兼容链路；新的 Qwen3-Coder vLLM 作为 coding-agent 主线单独维护。当前已完成“逻辑分线”，但尚未执行旧模型物理删除。
15. 进一步推进退役旧 8B 时，`download_llm_model.sh` 已经显式拒绝 `qwen3-8b-awq` 作为活跃下载目标，并改为提示使用 `setup_qwen3_coder_vllm.sh` / `start_qwen3_coder_vllm.sh`。这意味着旧 8B 已经从“推荐安装路径”里移除，但 `run_all.sh` 与旧 smoke 兼容路径仍暂时保留默认值，物理删除还需最后一步确认。
16. 又进一步收缩 verify 默认行为：`verify_all.sh` 与 `start_server_workflow.sh` 现在默认不再自动跑旧 `qwen3-8b-awq` extractor 检查，只有显式设置 `USE_LEGACY_QWEN_EXTRACTOR=1` 才会继续执行旧 smoke / 小样本抽取。当前仓库已经进入“默认主线=Qwen3-Coder vLLM，旧 8B=手动按需兼容路径”的状态。
17. 继续收尾时，`setup_server_all.sh` 已正式切到 Qwen3-Coder vLLM 主线，一键入口会直接走 `setup_qwen3_coder_vllm.sh` + `start_qwen3_coder_vllm.sh`；同时 `run_all.sh` 不再自动依赖旧 8B 本地抽取链路，缺失结构化事件文件时会直接提示先通过维护中的上游抽取流程生成。当前旧 8B 只剩手动兼容角色，已经接近可以物理删除。
18. 已按用户要求正式删除远端旧模型目录：`/root/autodl-tmp/models/qwen3-8b-awq`。删除前体积约 5.7G；删除后 `/root/autodl-tmp/models` 下仅保留 `qwen3-coder-30b-a3b-instruct-fp8`，数据盘可用空间约 397G。

# sanmao-quant-llm 工程部署记录

生成日期：2026-05-30

## 当前阶段目标

先构建离线金融量化研究工程，不接入真实股票账户，不保存券商凭据，不执行真实交易。

本阶段只验证：

1. 公开价格数据下载。
2. 技术特征生成。
3. 机器学习 baseline 训练。
4. walk-forward 回测。
5. Parquet + DuckDB 特征/预测落地。

## 服务器

```bash
ssh seeta-gpu
```

工程目录：

```bash
/root/autodl-tmp/sanmao-quant-llm
```

本地 GitHub 工程目录：

```bash
/Users/wumin/Documents/Obsidian Vault/论文研究/量化研究/开发部署/sanmao-quant-llm
```

Python 环境：

```bash
/root/autodl-tmp/sanmao-quant-llm/.venv
```

## 安全边界

当前不会接入：

1. 真实股票账户。
2. 券商 API key。
3. 券商登录密码。
4. 自动下单逻辑。

真实账户接入必须等离线回测和 paper trading 验证通过后再做。

## 已创建工程结构

```text
sanmao-quant-llm/
  config/
    baseline.yaml
  scripts/
    run_baseline.py
  src/
    quant_llm/
      backtest.py
      config.py
      data.py
      features.py
      modeling.py
  tests/
    test_features.py
  pyproject.toml
  README.md
```

## baseline 设计

数据源：Yahoo Finance chart 日线接口，失败时允许使用合成行情 fallback 验证工程链路。

备注：最初尝试 Stooq CSV，但 2026-05-30 实测该接口返回 API key/captcha 提示，不再适合作为无账号自动化 baseline 数据源，因此改用 Yahoo chart 公开接口。

2026-05-30 进一步实测：GPU 服务器访问 Yahoo chart 返回 HTTP 403。当前 baseline 启用 `allow_synthetic_fallback: true`，用于验证工程链路和回测输出格式。合成行情不能作为策略有效性证据，只能证明代码路径可运行。后续需要接入稳定数据源，例如付费行情、Polygon、Tiingo、Alpha Vantage、券商历史行情、Nasdaq Data Link 或本地已下载数据。

默认股票池：

```text
AAPL.US
MSFT.US
NVDA.US
SPY.US
```

特征：

```text
ret_1d
ret_5d
ret_20d
vol_20d
ma_gap_10d
ma_gap_50d
range_1d
volume_z_20d
```

标签：

```text
target_up = next_day_return > 0
```

模型：

1. 优先 XGBoost。
2. 如果 XGBoost 不可用，fallback 到 RandomForest。

回测：

1. walk-forward 训练/测试切分。
2. `prob_up >= 0.55` 时 next-day long，否则空仓。
3. 默认交易成本 5 bps。
4. 输出总收益、年化收益、波动、Sharpe、最大回撤、换手率、暴露度。

## 运行命令

```bash
ssh seeta-gpu
cd /root/autodl-tmp/sanmao-quant-llm
.venv/bin/python scripts/run/run_baseline.py --config config/baseline.yaml
```

## 输出目录

```text
/root/autodl-tmp/sanmao-quant-llm/data/
/root/autodl-tmp/sanmao-quant-llm/reports/
```

关键文件：

```text
data/features/prices.parquet
data/features/price_features.parquet
data/quant.duckdb
reports/predictions.parquet
reports/metrics.json
```

## 下一步

1. 接入稳定历史行情源，替换合成 fallback。
2. 加 LLM 文本特征模块。
3. 扩展特征库 schema。
4. 引入更严格的 walk-forward、交易成本、滑点和风险约束。
5. 再进入 paper trading 设计。

## 操作注意

从本机同步代码到服务器时，不要使用会删除远端环境和结果的裸 `rsync --delete`。

推荐：

```bash
rsync -az --delete \
  --exclude .git \
  --exclude .venv \
  --exclude data \
  --exclude reports \
  "/Users/wumin/Documents/Obsidian Vault/论文研究/量化研究/开发部署/sanmao-quant-llm/" \
  seeta-gpu:/root/autodl-tmp/sanmao-quant-llm/
```

原因：`.venv`、`data/`、`reports/` 是服务器侧生成资产，应保留在数据盘。

## 2026-05-30 验证结果

服务器命令：

```bash
cd /root/autodl-tmp/sanmao-quant-llm
.venv/bin/pytest -q
.venv/bin/python scripts/run/run_baseline.py --config config/baseline.yaml
```

测试结果：

```text
2 passed in 1.14s
```

baseline 输出：

```text
prices rows: 8780
features rows: 8580
predictions rows: 5556
```

生成文件：

```text
data/features/prices.parquet
data/features/price_features.parquet
data/quant.duckdb
reports/predictions.parquet
reports/metrics.json
```

DuckDB 视图验证：

```text
select count(*) from price_features -> 8580
select count(*) from predictions -> 5556
```

回测 smoke test 指标：

```json
{
  "total_return": -0.27137795201938164,
  "annual_return": -0.05582083101064794,
  "annual_volatility": 0.0526241747311716,
  "sharpe": -1.0607450149252948,
  "max_drawdown": -0.3058408490832092,
  "mean_daily_turnover": 0.2991360691144708,
  "hit_rate_when_in_market": 0.4782608695652174,
  "exposure": 0.24010079193664507
}
```

解释：这是合成行情 fallback 上的工程链路验证，只证明 pipeline 能完整运行并产出格式正确的结果，不能证明策略有效。

## 2026-05-30 GitHub 工程化整理

已将代码工程迁移到 Obsidian 目录下，作为后续上传 GitHub 的项目根目录：

```bash
/Users/wumin/Documents/Obsidian Vault/论文研究/量化研究/开发部署/sanmao-quant-llm
```

新增 GitHub 项目文件：

```text
.gitignore
.env.example
LICENSE
README.md
docs/ARCHITECTURE.md
docs/CODE_WALKTHROUGH.md
docs/SERVER_DEPLOYMENT.md
docs/ROADMAP.md
```

本地项目已执行：

```bash
git init
```

从新项目目录同步到服务器后重新验证：

```text
2 passed in 1.19s
baseline pipeline completed
```

说明：后续应以 `开发部署/sanmao-quant-llm` 为代码源，服务器 `/root/autodl-tmp/sanmao-quant-llm` 作为运行环境。项目名是 `sanmao-quant-llm`，Python 包名暂时保留为 `quant_llm`。

## 2026-05-30 项目改名和中文文档

根据后续命名要求，代码工程从 `quant-llm` 改为：

```text
sanmao-quant-llm
```

本地代码源：

```bash
/Users/wumin/Documents/Obsidian Vault/论文研究/量化研究/开发部署/sanmao-quant-llm
```

服务器运行目录：

```bash
/root/autodl-tmp/sanmao-quant-llm
```

已更新：

1. `pyproject.toml` 项目名：`sanmao-quant-llm`
2. README 和 docs 改成中文为主，关键英文术语括注。
3. `config/baseline.yaml` 输出路径改到 `/root/autodl-tmp/sanmao-quant-llm`。
4. `docs/SERVER_DEPLOYMENT.md` 同步命令和服务器路径改成新项目名。

服务器新目录验证：

```text
pip installed package: sanmao-quant-llm-0.1.0
pytest: 2 passed in 1.16s
baseline pipeline completed
```

说明：旧服务器目录 `/root/autodl-tmp/quant-llm` 已删除。后续唯一服务器工作目录是 `/root/autodl-tmp/sanmao-quant-llm`。

## 2026-05-30 文档可读性修正

根据反馈，原文档对量化初学者不够友好，已做以下修正：

1. `config/baseline.yaml` 增加逐项中文注释，解释每个字段是什么、为什么这样设置。
2. 新增 `docs/CONCEPTS.md`，详细解释特征、样本外、walk-forward、look-ahead leakage、long/flat、交易成本、回测指标、AUC、log_loss、Parquet、DuckDB、滑点、滑点模型、对账、实时与批处理。
3. `README.md` 增加“当前预测目标”和文档阅读顺序。
4. `ARCHITECTURE.md` 增加系统如何服务于最终智能买入/卖出的说明。
5. `CODE_WALKTHROUGH.md` 增加更多例子，解释 `prob_up >= threshold -> long` 等代码含义。
6. 关键代码增加注释，重点解释 `walk_forward_predict`、XGBoost 参数、特征计算和 backtest 收益计算。
7. 新增 `scripts/env/bootstrap_server.sh`，用于 GPU 服务器关机后快速恢复环境。

后续文档要求：中文为主，关键英文术语括注；新概念必须解释“是什么、为什么要这样、和最终交易目标有什么关系”，配置和关键代码也要有必要注释。

## 2026-05-30 模型策略和市场数据状态

本轮明确了架构策略：

1. 不一开始下载多个 32B 大模型，避免浪费 50GB 数据盘和 GPU 费用。
2. 当前已下载大模型：0 个。
3. 当前建议下一步最多下载 1 个文本抽取模型，优先 14B 级别；市场数据和文本特征表稳定后再考虑 32B。
4. DeepSeek-R1-Distill-Qwen-32B 和 Qwen2.5-Coder-32B 暂不下载。
5. 详细说明见 `sanmao-quant-llm/docs/MODEL_STRATEGY.md`。

市场数据状态：

1. 代码已新增 `market_data_provider: "yfinance"` 配置。
2. 新增 `scripts/verify/check_market_data.py`，用于检查 provider 是否返回真实行情。
3. GPU 服务器实测 yfinance 返回限流错误：`YFRateLimitError('Too Many Requests. Rate limited. Try after a while.')`。
4. baseline 可以继续跑通，但当前实际使用 `synthetic_fallback`，不是实时/真实市场数据。
5. 下一步需要接稳定数据源：付费 API、券商历史行情只读接口、或本地 CSV/Parquet 数据导入。

验证：

```text
pytest: 2 passed in 1.16s
baseline completed with providers_used ['synthetic_fallback']
```

## 2026-05-31 市场数据源扩展

参考用户提供的数据源列表和官方 API 文档后，新增 provider：

```text
alpha_vantage
tiingo
```

使用方式：

```bash
export ALPHA_VANTAGE_API_KEY="..."
export TIINGO_API_KEY="..."
.venv/bin/python scripts/verify/check_market_data.py --provider tiingo
.venv/bin/python scripts/verify/check_market_data.py --provider alpha_vantage
```

同时新增：

```text
docs/MARKET_DATA.md
```

用于说明 Yahoo/yfinance、Alpha Vantage、Tiingo、Finnhub、Nasdaq Data Link/Quandl 的取舍。

用户提供的值得买参考链接：

```text
https://post.smzdm.com/p/a3meqlmr/
```

本地抓取该链接时 `baoyu-fetch` 的 Bun 依赖报错，未成功提取正文。该链接暂作为待人工补充参考；当前实现依据优先使用官方 API 文档。

修正：

1. raw 缓存文件名加入 provider 前缀，避免 `synthetic` 缓存污染 `alpha_vantage` / `tiingo` 检查。
2. `check_market_data.py` 不再把 `synthetic` 当成真实市场数据。

## 2026-05-31 Tiingo 真实行情接入成功

用户已提供 Tiingo API token。Token 已写入服务器：

```bash
/root/autodl-tmp/sanmao-quant-llm/.env
```

安全说明：

1. `.env` 权限为 600。
2. `.env` 不同步到 Git 仓库。
3. 文档不记录 token 明文。

代码更新：

1. `run_baseline.py` 和 `check_market_data.py` 会自动读取项目根目录 `.env`。
2. `config/baseline.yaml` 已切换为 `market_data_provider: "tiingo"`。
3. `allow_synthetic_fallback` 已改为 `false`，真实行情失败时会直接报错，避免误用合成数据。
4. Tiingo provider 使用 adjusted OHLCV 字段，适合历史回测。

验证命令：

```bash
cd /root/autodl-tmp/sanmao-quant-llm
.venv/bin/pytest -q
.venv/bin/python scripts/verify/check_market_data.py --provider tiingo
.venv/bin/python scripts/run/run_baseline.py --config config/baseline.yaml
```

验证结果：

```text
pytest: 2 passed in 1.23s
check_market_data: is_real_market_data = true
providers_used: ['tiingo']
rows: 8452
symbols: ['AAPL.US', 'MSFT.US', 'NVDA.US', 'SPY.US']
date_range: 2018-01-02 -> 2026-05-29
```

真实 Tiingo baseline 指标：

```json
{
  "rows": 5228.0,
  "days": 1307.0,
  "total_return": 0.1411213843530339,
  "annual_return": 0.025779547708715267,
  "annual_volatility": 0.15935551741011192,
  "sharpe": 0.16177380066715796,
  "max_drawdown": -0.3734035533957769,
  "mean_daily_turnover": 0.40990818668706963,
  "hit_rate_when_in_market": 0.5258037225042301,
  "exposure": 0.4521805661820964
}
```

解释：这只是价格特征 baseline，已经用真实 Tiingo 历史行情跑通，但策略质量还很弱，不能用于实盘。下一步应该加入更稳的数据验证、更多标的、更严格回测和 LLM 文本特征。

## 2026-05-31 新闻/舆情文本特征第一版全链路跑通

目标：在不接券商真实交易账户、不急着下载大模型的前提下，先把新闻/舆情文本特征 pipeline 跑通。

实现：

1. 新增 `data_samples/news/sample_news.csv` 样例新闻。
2. 新增 `src/quant_llm/text_features.py`。
3. 当前使用 `RuleBasedTextExtractor` 模拟未来 LLM JSON 输出。
4. 新增 `TEXT_FEATURE_COLUMNS` 并合并到模型训练特征。
5. `run_baseline.py` 会保存：
   - `text_events.parquet`
   - `daily_text_features.parquet`
   - `training_features.parquet`
6. 新增 `tests/test_text_features.py`。

服务器验证：

```text
pytest: 3 passed in 1.21s
providers_used: ['tiingo']
text_events: 17
daily_text_features: 17
training_features: 8252
```

本轮 feature columns：

```text
ret_1d
ret_5d
ret_20d
vol_20d
ma_gap_10d
ma_gap_50d
range_1d
volume_z_20d
llm_news_count
llm_mean_sentiment
llm_weighted_sentiment
llm_max_confidence
event_earnings_count
event_macro_count
risk_margin_pressure_count
risk_guidance_weak_count
risk_supply_chain_count
```

真实 Tiingo + 文本特征 baseline 指标：

```json
{
  "total_return": 0.30964504247722235,
  "annual_return": 0.05338746706169806,
  "annual_volatility": 0.15605299710784842,
  "sharpe": 0.34211112923901044,
  "max_drawdown": -0.34428284147542554,
  "mean_daily_turnover": 0.4026396327467483,
  "hit_rate_when_in_market": 0.534923339011925,
  "exposure": 0.44912012241775057
}
```

解释：这证明“真实行情 + 新闻文本特征 + 模型 + 回测”全链路跑通。但当前新闻是少量样例，抽取器是规则模拟，不代表真实 LLM 舆情策略有效。下一步应接真实新闻源和真实 LLM extractor。

## 2026-05-31 Tiingo News 权限验证

用户说明 News token 与 Tiingo token 相同。服务器已用当前 `TIINGO_API_KEY` 验证 Tiingo News：

```text
status: 403
{"detail":"You do not have permission to access the News API"}
```

结论：

1. 当前 token 可用于 Tiingo daily prices。
2. 当前 token 暂无 Tiingo News API 权限。
3. 已新增 `src/quant_llm/news.py` 和 `scripts/run/fetch_tiingo_news.py`，后续开通权限后可直接拉取新闻 CSV。
4. 当前新闻/舆情全链路继续使用 `data_samples/news/sample_news.csv` 作为样例数据。

## 2026-05-31 SEC EDGAR 免费公告源接入成功

由于 Tiingo News 当前无权限，先接入免费官方数据源 SEC EDGAR。

实现：

1. `fetch_sec_filings`：ticker -> CIK -> SEC submissions recent filings。
2. `scripts/run/fetch_sec_filings.py`：拉取 8-K、10-Q、10-K 并保存为统一 news CSV schema。
3. `config/sec_filings_baseline.yaml`：Tiingo 真实日线 + SEC filings 文本特征 baseline。

服务器验证：

```text
pytest: 5 passed in 6.38s
SEC filings rows: 150
forms: ['10-K', '10-Q', '8-K']
```

SEC filings baseline：

```text
providers: ['tiingo']
text_events: 150
daily_text_features: 125
training_features: 5228
```

指标：

```json
{
  "total_return": 0.18655072856054966,
  "annual_return": 0.08137136273909307,
  "annual_volatility": 0.1567866716187091,
  "sharpe": 0.5189941332320697,
  "max_drawdown": -0.16150671084596313,
  "mean_daily_turnover": 0.40063520871143377,
  "hit_rate_when_in_market": 0.5547290116896918,
  "exposure": 0.42695099818511795
}
```

解释：SEC EDGAR 是免费公告/监管文件源，不是新闻媒体源。它已经让“免费事件文本 + Tiingo 行情 + 文本特征 + 模型 + 回测”跑通。当前抽取仍是规则模拟 LLM，后续要替换真实 LLM extractor。

## 2026-05-31 本地 LLM extractor 接入尝试

目标模型：

```text
Qwen/Qwen3-8B-AWQ
```

原因：

1. 第一版任务是 JSON 结构化抽取，不是复杂推理。
2. 8B 比 32B 更省磁盘和显存。
3. 当前数据盘只有 50GB，不适合一次下载多个大模型。

已完成：

1. 新增 `src/quant_llm/llm_extractor.py`。
2. 新增 `scripts/run/extract_news_with_llm.py`。
3. 新增 `tests/test_llm_extractor.py`。
4. `download_llm_model.sh` 增加 `qwen3-8b-awq` alias。

安装尝试结果：

```text
pip install -e ".[llm]"
```

在项目 `.venv` 中会尝试重新下载 Torch 2.12 和大量 CUDA 13 依赖包，而服务器系统环境原本已有 PyTorch 2.8.0+cu128。为了避免浪费 GPU 计费时间和 50GB 数据盘，已中止这次安装。

结论：

```text
不要在当前项目 .venv 里直接安装完整 LLM 推理栈。
```

后续更稳方案：

1. 复用系统 `/root/miniconda3/bin/python` 的 PyTorch 环境单独跑 LLM extractor。
2. 或创建独立 `llm` conda/venv 环境，避免污染量化 baseline 环境。
3. 或使用 llama.cpp / GGUF 小模型，减少 Python CUDA 依赖问题。
4. 或先用 API LLM 跑 extractor，等 pipeline 稳定后再切本地模型。

当前状态：

```text
LLM extractor 接口已写好
Qwen3-8B-AWQ 尚未成功下载/部署
规则抽取器仍是当前 pipeline 默认可运行路径
```

后续继续验证：

1. 系统 Python 已有 `torch 2.8.0+cu128`。
2. 已尝试只安装轻量依赖 `transformers/accelerate/huggingface_hub/safetensors`，未重新安装 torch。
3. Hugging Face 下载 `Qwen/Qwen3-8B-AWQ` 时服务器返回 `Network is unreachable`，模型没有落地。
4. 系统 Python 中 `transformers` 因 `tokenizers==0.23.1` 超出其要求范围而导入失败；阿里源没有 `tokenizers==0.23.0` 正式包。
5. 为避免破坏系统 PyTorch/Jupyter 环境，暂停继续修系统包。

下一步建议：

```text
优先使用 ModelScope/魔搭下载 Qwen 模型，或创建独立 llm 环境。
不要继续污染当前量化 .venv，也不要继续改系统环境。
```

当前全链路仍可用：

```text
Tiingo + SEC/GDELT + RuleBasedTextExtractor + ML baseline + 回测
```

## 当前已知问题

1. Stooq 当前要求 API key/captcha，不能作为无账号自动化数据源。
2. GPU 服务器访问 Yahoo chart 返回 HTTP 403。
3. 当前 baseline 使用合成行情 fallback，策略指标没有投资含义。
4. 数据盘 50GB 足够当前工程，但不够长期保存多个 32B 模型和大规模行情/新闻数据。
5. 暂未部署 LLM 服务，当前完成的是量化工程 baseline。

## 2026-05-31 LLM confidence 概念补充

用户追问：LLM 是怎么根据文本评估 `confidence`、`sentiment` 等字段的。

补充说明：

1. `confidence` 是 LLM 对“文本结构化抽取是否可靠”的置信度，不是股票上涨概率。
2. `prob_up` 才是 ML 模型综合价格特征和文本特征后输出的上涨概率。
3. Prompt 中已明确要求：
   - 0.85-0.95：公司、事件、方向、风险都明确。
   - 0.55-0.75：相关但好坏混合、表达模糊或需要部分推断。
   - 0.20-0.50：ticker 关联或金融影响较弱。
4. 代码已在 `src/quant_llm/llm_extractor.py` 中增加 LLM 输出防护：
   - `sentiment` 裁剪到 `[-1, 1]`。
   - `confidence` 裁剪到 `[0, 1]`。
   - 未知 `event_type` 归为 `other`。
   - 未知 `impact_horizon` 归为 `1-5d`。
5. 新增测试覆盖异常 LLM 输出归一化，避免脏 JSON 直接进入特征库。

详细解释见：

```text
docs/CONCEPTS.md
```

## 2026-05-31 服务器代理与 Qwen 下载进展

用户指出：Hugging Face 下载失败可能是因为服务器没有设置代理，本机已有网络代理。

核查结果：

1. 服务器系统 PyTorch/CUDA 可用，不是 GPU 环境坏了：

```text
Python 3.12.3
torch 2.8.0+cu128
torch.cuda.is_available() == True
```

2. 系统 Python 的问题是 `transformers/tokenizers` 版本冲突：

```text
transformers requires tokenizers>=0.22.0,<=0.23.0
but found tokenizers==0.23.1
```

3. 服务器直连 Hugging Face 超时。
4. 本机 ClashX 监听 `127.0.0.1:7890`。
5. 通过 SSH 反向端口转发后，服务器可以经由 `127.0.0.1:7890` 访问 Hugging Face：

```text
HTTP/2 200
huggingface.co reachable
```

已完成：

1. 创建独立 LLM 环境 `/root/autodl-tmp/llm-env`。
2. 该环境使用 `--system-site-packages` 复用系统 CUDA PyTorch。
3. 在独立环境中安装并验证：

```text
torch 2.8.0+cu128 cuda True
transformers 4.57.1
tokenizers 0.22.1
```

4. 开始下载 `Qwen/Qwen3-8B-AWQ` 到：

```text
/root/autodl-tmp/models/qwen3-8b-awq
```

5. 已新增脚本：

```text
scripts/env/open_hf_proxy_tunnel.sh
scripts/env/download_llm_model.sh
```

当前中断点：

```text
Qwen/Qwen3-8B-AWQ 下载过程中，SSH 连接被远端断开。
之后尝试重连 seeta-gpu，服务器 18050 端口返回 Connection refused。
```

结论：

```text
Qwen 还没有完整部署好。
LLM Python 环境已经修好。
代理方案已经验证可行。
等服务器 SSH 恢复后，继续运行 bash scripts/env/download_llm_model.sh qwen3-8b-awq 即可断点续传。
```

## 2026-05-31 Qwen3-8B-AWQ 本地 LLM 部署成功

用户提供新 SSH 登录地址：

```text
ssh -p 53036 root@connect.westd.seetacloud.com
```

已更新本地 `ssh seeta-gpu` 配置：

```text
HostName connect.westd.seetacloud.com
Port 53036
User root
IdentityFile /Users/wumin/.ssh/id_ed25519
```

已用密码登录一次，并把本机公钥写入服务器：

```text
/root/.ssh/authorized_keys
```

后续 `ssh seeta-gpu` 已恢复免密登录。

### Qwen 下载与环境

已通过本机 ClashX 代理 + SSH 反向端口转发下载：

```text
Qwen/Qwen3-8B-AWQ
```

模型目录：

```text
/root/autodl-tmp/models/qwen3-8b-awq
```

LLM 环境：

```text
/root/autodl-tmp/llm-env
```

关键依赖：

```text
torch 2.8.0+cu128
autoawq 0.2.9
transformers 4.51.3
tokenizers 0.21.4
```

说明：

1. Qwen3-8B-AWQ 是 AWQ 量化模型，加载需要 `autoawq`。
2. `autoawq` 与 `transformers 4.57.1` 不兼容，会报 `PytorchGELUTanh` 导入错误。
3. 已将 LLM 环境降到 `transformers 4.51.3` 和 `tokenizers 0.21.x`。
4. AutoAWQ 官方提示已 deprecated，后续生产化更建议 vLLM 或其他维护更活跃的推理栈。

### 验证结果

Smoke test：

```text
generated: {"event_type":"earnings","sentiment":0.3,"confidence":0.85,"impact_horizon":"1-5d","risk_tags":["margin_pressure"]}
parsed: {"confidence": 0.85, "event_type": "earnings", "impact_horizon": "1-5d", "risk_tags": ["margin_pressure"], "sentiment": 0.3}
```

正式 extractor 样例：

```bash
HF_HOME=/root/autodl-tmp/hf \
  /root/autodl-tmp/llm-env/bin/python scripts/run/extract_news_with_llm.py \
  --news-csv data_samples/news/sample_news.csv \
  --output data/news/qwen_sample_events.csv \
  --model-path /root/autodl-tmp/models/qwen3-8b-awq \
  --limit 3
```

输出：

```text
saved 3 extracted events to /root/autodl-tmp/sanmao-quant-llm/data/news/qwen_sample_events.csv
```

样例 CSV：

```text
date,symbol,event_type,sentiment,confidence,impact_horizon,risk_tags
2021-01-27,AAPL.US,earnings,1.0,0.95,1-5d,[]
2021-04-28,AAPL.US,earnings,0.3,0.85,1-20d,['supply_chain']
2022-01-27,AAPL.US,supply_chain,-0.3,0.85,1-20d,['supply_chain']
```

量化工程回归测试：

```text
pytest: 8 passed in 7.24s
```

当前结论：

```text
Qwen3-8B-AWQ 本地模型已下载、可加载、可生成金融文本 JSON 特征。
下一步是把 Qwen extractor 接到 SEC/GDELT/Tiingo 可用文本源的批处理 pipeline，并比较 RuleBasedTextExtractor vs Qwen extractor 的特征和回测差异。
```

## 2026-05-31 LLM 部署脚本和环境清理

用户追问：

1. 是否有两套 `transformers`？
2. 没用的版本为什么不删？
3. `risk_tags=[]` 是什么意思？
4. 后续换机器部署，需要一键部署脚本和一键启动脚本。
5. 下载模型遇到的问题和解决经验要整理成文档。

处理结果：

### transformers 环境清理

确认曾经有两套：

```text
系统 Python：transformers 5.9.0 + tokenizers 0.23.1，冲突，不用于当前工程。
LLM 环境：transformers 4.51.3 + tokenizers 0.21.4，用于 Qwen。
```

已删除系统 Python 中误装且不用的：

```text
transformers 5.9.0
tokenizers 0.23.1
```

验证结果：

```text
system transformers removed or unavailable
llm-env transformers 4.51.3
llm-env tokenizers 0.21.4
llm-env torch 2.8.0+cu128 True
```

### risk_tags=[] 解释

`risk_tags=[]` 是空数组，表示：

```text
这条新闻/公告没有抽取到明确风险标签。
```

不是错误。比如强利好的财报新闻，可能 `event_type=earnings`、`sentiment=1.0`、`confidence=0.95`，但没有 margin pressure、supply chain 等风险，因此 `risk_tags=[]`。

### 新增脚本

新增一键完整部署脚本：

```text
scripts/env/setup_server_all.sh
```

作用：

1. 创建/更新量化 `.venv`。
2. 创建/更新 `/root/autodl-tmp/llm-env`。
3. 下载 `Qwen/Qwen3-8B-AWQ`。
4. 运行 Qwen JSON smoke test。
5. 运行项目测试。

新增一键启动/验证脚本：

```text
scripts/verify/start_server_workflow.sh
```

作用：

1. 跑项目测试。
2. 跑 SEC + Tiingo baseline。
3. 跑 Qwen smoke test。
4. 跑 Qwen 样例新闻抽取。

新增部署经验文档：

```text
docs/LLM_DEPLOYMENT_NOTES.md
```

记录内容：

1. 两套 Python 环境的分工。
2. AutoAWQ 和 transformers 版本兼容问题。
3. Hugging Face 代理隧道方案。
4. 断点续传和下载卡住时的处理经验。
5. Qwen3 `/no_think` 和 JSON-only prompt 经验。
6. `risk_tags=[]` 的含义。

## 2026-05-31 scripts 目录重构

用户指出：当前代码结构不清晰，`scripts/` 下把环境准备、正式运行、测试验证混在一起。

已重构为三类目录：

```text
scripts/env/      环境准备：装依赖、下载模型、开代理隧道
scripts/run/      正式运行：拉数据、生成特征、训练、回测、LLM 抽取
scripts/verify/   测试验证：检查行情、检查 Qwen、开机后一键验证
```

当前脚本分布：

```text
scripts/env/bootstrap_server.sh
scripts/env/download_llm_model.sh
scripts/env/open_hf_proxy_tunnel.sh
scripts/env/setup_server_all.sh
scripts/run/extract_news_with_llm.py
scripts/run/fetch_gdelt_news.py
scripts/run/fetch_sec_filings.py
scripts/run/fetch_tiingo_news.py
scripts/run/run_baseline.py
scripts/run/run_sec_pipeline.sh
scripts/verify/check_market_data.py
scripts/verify/smoke_llm_qwen.py
scripts/verify/start_server_workflow.sh
```

同时新增：

```text
scripts/README.md
```

说明三类目录的边界和使用原则。

已同步更新：

1. README。
2. SERVER_DEPLOYMENT。
3. PIPELINE_DATA_FLOW。
4. LLM_DEPLOYMENT_NOTES。
5. 相关脚本内部调用路径。
6. `tests/test_duckdb_literal.py`。

服务器验证：

```text
bash -n: passed
py_compile: passed
pytest: 8 passed
Qwen smoke test: parsed JSON 成功
```

## 2026-05-31 run_all 总入口和 Qwen 自动接入

用户指出：如果使用 Qwen，还要手动先跑 `extract_news_with_llm.py`，再跑训练脚本，这不合理。`scripts/run/` 也缺少带 `all` 字样的总入口。

已实现：

```text
scripts/run/run_all.sh
```

它是正式研究链路总入口，一次完成：

```text
取 SEC 数据
-> 检查/生成 Qwen 结构化事件 CSV
-> 读取 Qwen events_csv
-> 拼接价格特征和文本特征
-> walk-forward 训练/预测
-> 回测
-> 输出 metrics/predictions/training_features/DuckDB
```

新增 Qwen 配置：

```text
config/sec_filings_qwen.yaml
```

关键字段：

```yaml
text_features:
  enabled: true
  events_csv: "/root/autodl-tmp/sanmao-quant-llm/data/news/sec_filings_qwen_events.csv"
```

`run_baseline.py` 已支持两种文本输入：

```text
news_csv    原始文本 CSV，使用 RuleBasedTextExtractor 现场抽取
events_csv  已由 Qwen/LLM 抽取好的结构化事件 CSV
```

新增 `src/quant_llm/text_features.py` 能读取 Qwen events CSV：

```text
load_text_events_csv
parse_risk_tags
```

新增 verify 总入口：

```text
scripts/verify/verify_all.sh
```

验证命令：

```bash
LLM_LIMIT=5 bash scripts/run/run_all.sh
```

验证结果：

```text
saved 150 SEC filing rows to data/news/sec_filings.csv
saved 5 extracted events to data/news/sec_filings_qwen_events.csv
training_features: 5228
predictions: 2204
pytest: 8 passed
```

说明：验证时用 `LLM_LIMIT=5` 是为了省 GPU 时间。全量 Qwen 抽取可运行：

```bash
LLM_LIMIT=0 bash scripts/run/run_all.sh
```

## 2026-05-31 模型持久化和直观收益报告

用户追问：

1. 回测的作用是什么？
2. 回测完是否更新模型？
3. 模型保存在哪里？
4. 哪个文件能直观看到收益？
5. 后续模拟盘应该加载谁？

已补齐工程产物：

```text
models/<strategy_id>/latest_model.joblib
models/<strategy_id>/latest_model_metadata.json
reports/<strategy_id>/backtest_daily.csv
reports/<strategy_id>/backtest_daily.parquet
reports/<strategy_id>/backtest_positions.parquet
reports/<strategy_id>/latest_signals.csv
scripts/verify/show_report.py
```

关键解释：

```text
walk-forward 临时模型：只用于历史回测评估，不保存。
latest_model.joblib：回测完成后，用全部已有 training_features 重新训练出来，给后续模拟盘/应用加载。它保存在 `models/<strategy_id>/` 下面，不同市场/策略不能共用同一个文件。
```

回测本身不会在线更新模型。当前 pipeline 是：

```text
先 walk-forward 回测评估
再 fit_final_model(...)
再 joblib.dump(..., models/<strategy_id>/latest_model.joblib)
```

服务器验证：

```text
bash scripts/run/run_all.sh
```

输出摘要：

```text
Total return:      15.78%
Annual return:     6.93%
Annual volatility: 14.83%
Sharpe:            0.468
Max drawdown:      -14.75%
Exposure:          42.79%
```

最新信号：

```text
2026-05-28 AAPL.US prob_up=0.484137 flat
2026-05-28 MSFT.US prob_up=0.578552 long
2026-05-28 NVDA.US prob_up=0.409764 flat
2026-05-28 SPY.US  prob_up=0.482150 flat
```

当前判断：

```text
这只是研究回测结果，不足以上实盘。
下一步应该做 paper trading / 模拟盘：
  1. 每日生成最新特征。
  2. 加载 models/<strategy_id>/latest_model.joblib。
  3. 输出 prob_up 和 long/flat。
  4. 写模拟账户 ledger。
  5. 连续观察稳定性后再考虑小权限实盘。
```

## 2026-06-01 旧共享产物清理

用户指出“没用的东西肯定要删，但要确保真的没用了”。本次先做引用检查，再删除旧生成产物。

检查结果：

```text
当前所有 config/*.yaml 都已经使用 strategy_id 隔离：
data/<strategy_id>/
reports/<strategy_id>/
models/<strategy_id>/
```

删除的只是服务器旧共享路径下的生成产物，不包含源码、配置、.env、虚拟环境和新策略目录：

```text
data/features/
data/news/
data/raw/
data/checks/
data/quant.duckdb
reports/backtest_daily.csv
reports/backtest_daily.parquet
reports/backtest_positions.parquet
reports/latest_signals.csv
reports/metrics.json
reports/predictions.parquet
reports/paper_trading/
models/candidate_model.joblib
models/candidate_model_metadata.json
models/latest_model.joblib
models/latest_model_metadata.json
```

这些文件属于旧版共享目录产物，存在覆盖风险：

```text
美股/A 股/港股或同一市场不同策略可能写同名 training_features、metrics、latest_model。
```

清理后的正确输出位置示例：

```text
data/us_sec_qwen_xgboost_v1/features/training_features.parquet
reports/us_sec_qwen_xgboost_v1/metrics.json
models/us_sec_qwen_xgboost_v1/latest_model.joblib
```

服务器验证：

```text
.venv/bin/python -m pytest
39 passed
```
