# scripts 目录说明

脚本按用途分成三个目录，避免把部署、正式运行、验证脚本混在一起。

## env：环境准备

```text
scripts/env/
```

只放“准备机器和环境”的脚本。

| 脚本 | 用途 |
|---|---|
| `bootstrap_server.sh` | 创建/更新量化 `.venv`（含 anthropic），并建好 data/reports/logs/models 目录 |

总入口：

```bash
bash scripts/env/bootstrap_server.sh
```

说明：LLM 文本抽取走 Claude API（`anthropic` SDK），不需要 GPU、不下载模型权重，只需要一个 `ANTHROPIC_API_KEY`（见 `.env.example`）。

## run：正式运行

```text
scripts/run/
```

只放“产生研究数据/特征/回测结果”的脚本。

| 脚本 | 用途 |
|---|---|
| `fetch_sec_filings.py` | 下载 SEC 免费公告/财报 filings |
| `fetch_tiingo_news.py` | Tiingo News 拉取脚本，当前 token 无权限时不可用 |
| `fetch_gdelt_news.py` | GDELT 免费新闻拉取脚本 |
| `run_a_share_baostock.py` | 用 BaoStock 按配置批量拉取并缓存 A 股日线，不训练模型 |
| `build_a_share_universe.py` | 用 BaoStock 生成 A 股股票池文件，并做基础过滤 |
| `build_daily_universe_membership.py` | 把股票列表展开成逐日 `date,symbol` 股票池 CSV，供历史滚动过滤使用 |
| `build_baostock_historical_membership.py` | 用 BaoStock 按历史交易日生成 HS300/ZZ500/SZ50 的真实滚动 `date,symbol` 成份文件 |
| `extract_news_with_llm.py` | 用 Claude API 把新闻抽成 JSON 结构化事件（可 `--rule-fallback-only` 跳过 API） |
| `run_baseline.py` | 价格特征 + 文本特征 + ML + 回测主入口 |
| `run_paper_trading.py` | 加载 latest_model，生成模拟盘信号、模拟订单和持仓 |
| `run_paper_all.sh` | 先跑研究全链路，再跑第一版模拟盘 |
| `submit_alpaca_paper_orders.py` | 把模拟盘订单转换为 Alpaca paper API 订单；默认只预览不提交 |
| `run_sec_pipeline.sh` | SEC + Tiingo baseline 一键运行 |
| `run_all.sh` | run 目录总入口：取数据 -> LLM 抽取 -> 拼特征 -> 训练 -> 预测 -> 回测 |

总入口：

```bash
bash scripts/run/run_all.sh
```

训练/测试/预测/比较真实结果发生在：

```text
scripts/run/run_baseline.py
src/quant_llm/modeling.py
src/quant_llm/backtest.py
```

`run_baseline.py` 负责组织流程；`modeling.py` 做 walk-forward 训练和样本外预测；`backtest.py` 把预测概率和真实收益比较，计算策略结果。

Broker 相关代码按券商拆在：

```text
src/quant_llm/brokers/alpaca.py
src/quant_llm/brokers/qmt.py
src/quant_llm/brokers/futu.py
src/quant_llm/brokers/common.py
```

不要再把新券商逻辑堆进 `src/quant_llm/broker.py`；那个文件只做兼容导出。

## verify：测试验证

```text
scripts/verify/
```

只放“检查环境和 smoke test”的脚本。

| 脚本 | 用途 |
|---|---|
| `check_market_data.py` | 检查市场数据 provider 是否能返回真实行情 |
| `check_alpaca_paper.py` | 查看 Alpaca paper 账户、最近订单和持仓 |
| `check_futu_opend.py` | 检查富途牛牛/Moomoo OpenD 的 SDK、host/port 和 paper 模式 |
| `check_qmt_env.py` | 检查国金 QMT/miniQMT 的 xtquant、账号和客户端路径配置 |
| `show_report.py` | 读取最近一次回测结果，直观打印收益、回撤、最新信号 |
| `verify_all.sh` | verify 目录总入口 |

总入口：

```bash
bash scripts/verify/verify_all.sh
```

## 使用原则

1. 新机器部署：先看 `scripts/env/`。
2. 日常跑研究：看 `scripts/run/`。
3. 怀疑环境坏了：看 `scripts/verify/`。
4. 不要把安装依赖的逻辑写进 `scripts/run/`。
5. 不要把真实研究输出逻辑写进 `scripts/verify/`。
