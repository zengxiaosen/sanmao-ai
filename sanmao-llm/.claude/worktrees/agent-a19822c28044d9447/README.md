# sanmao-quant-llm

`sanmao-quant-llm` 是一个离线优先（offline-first）的金融量化研究工程。目标是把市场数据（market data）、新闻/舆情文本特征（text features）、机器学习模型（ML baseline）和回测（backtest）放进一个可复现、可上传 GitHub、可逐步扩展的工程里。

当前阶段是研究和工程验证，不连接真实股票账户，不下单，不保存券商密码或 API key。

当前已经接通 Alpaca Paper Trading 作为美股模拟盘/券商 paper account 验证，不连接真实资金账户。后续 A 股会单独接 QMT / PTrade 等适配层，市场规则与券商接口会保持分离。

港股路线优先考虑富途牛牛 / Moomoo OpenAPI。它需要先启动 OpenD 网关，再由 Python SDK 连接。当前项目已提供 OpenD 环境检测脚本，但还不会提交港股订单。

如果你刚开始看这个项目，建议先读：

1. [docs/CONCEPTS.md](docs/CONCEPTS.md)：解释特征、回测、walk-forward、Parquet、DuckDB、滑点等概念。
2. [docs/CODE_WALKTHROUGH.md](docs/CODE_WALKTHROUGH.md)：逐文件解释代码。
3. [docs/SERVER_DEPLOYMENT.md](docs/SERVER_DEPLOYMENT.md)：解释服务器启动和运行方式。
4. [docs/MODEL_STRATEGY.md](docs/MODEL_STRATEGY.md)：解释 API、自部署 LLM、传统 ML 的分工。
5. [docs/MARKET_DATA.md](docs/MARKET_DATA.md)：解释市场数据源选择和接入方式。
6. [docs/PIPELINE_DATA_FLOW.md](docs/PIPELINE_DATA_FLOW.md)：解释脚本之间怎么联动、文件写到哪里、特征怎么拼接。
7. [docs/A_SHARE_ADAPTER_PLAN.md](docs/A_SHARE_ADAPTER_PLAN.md)：解释 A 股、美股、港股多市场适配设计。

如果你关心“LLM 新闻特征怎么影响最终买卖概率”，直接看：

[docs/CONCEPTS.md#llm-结构化特征和预测概率是什么关系](docs/CONCEPTS.md#llm-结构化特征和预测概率是什么关系)

## 当前已经实现什么

当前 baseline 主要证明工程链路：

1. 加载日线 OHLCV 数据。
2. 生成价格/技术特征（price/technical features）。
3. 用 walk-forward 方式训练机器学习分类器。
4. 把预测概率转换成一个简单的 long/flat 策略。
5. 保存 Parquet 特征、DuckDB 视图、预测结果和 JSON 指标。

因为 GPU 服务器访问一些免费行情源受限，默认配置允许 synthetic fallback（合成行情 fallback）。这只能证明代码链路可运行，不能证明策略有效。

## 当前预测目标

当前模型预测的是：

```text
下一交易日 close 是否上涨
```

也就是：

```text
target_up = 明天 close / 今天 close - 1 > 0
```

模型输出 `prob_up`，表示“下一交易日上涨概率”。策略再用阈值决定：

```text
prob_up >= 0.55 -> long，买入/持有
prob_up < 0.55  -> flat，空仓
```

这只是第一版可解释 baseline。最终目标是接入真实行情和 LLM 文本特征，经过回测、模拟盘和风控后，才进入智能买入/卖出。

## 工程结构

```text
sanmao-quant-llm/
  config/
    baseline.yaml              # baseline 实验配置
  docs/
    ARCHITECTURE.md            # 架构和数据流说明
    CODE_WALKTHROUGH.md        # 代码逐文件解释
    CONCEPTS.md                # 量化概念解释
    PIPELINE_DATA_FLOW.md      # 脚本联动和文件数据流
    SERVER_DEPLOYMENT.md       # 服务器部署和运行说明
    ROADMAP.md                 # 后续路线图
  scripts/
    README.md                  # scripts/env/run/verify 三类脚本说明
    env/                       # 环境准备：依赖、模型、代理
    run/                       # 正式运行：拉数据、特征、训练、回测
    verify/                    # 测试验证：行情检查、Qwen smoke test
  src/
    quant_llm/
      backtest.py              # long/flat 回测指标
      config.py                # YAML 配置加载
      data.py                  # 行情加载和 synthetic fallback
      features.py              # 特征和标签生成
      modeling.py              # 模型创建和 walk-forward 预测
  tests/
    test_duckdb_literal.py
    test_features.py
  pyproject.toml
```

说明：项目名是 `sanmao-quant-llm`，Python 包名暂时保留为 `quant_llm`，这样 import 更简洁：

```python
from quant_llm.features import build_price_features
```

## 在 GPU 服务器上运行

```bash
ssh seeta-gpu
cd /root/autodl-tmp/sanmao-quant-llm
.venv/bin/pytest -q
bash scripts/run/run_all.sh
```

服务器重启或关机后恢复环境：

```bash
bash scripts/env/bootstrap_server.sh
```

输出文件：

```text
data/<strategy_id>/features/prices.parquet
data/<strategy_id>/features/price_features.parquet
data/<strategy_id>/features/training_features.parquet
data/<strategy_id>/quant.duckdb
reports/<strategy_id>/predictions.parquet
reports/<strategy_id>/metrics.json
models/<strategy_id>/candidate_model.joblib
models/<strategy_id>/latest_model.joblib
```

## 本地开发

如果在本地开发：

```bash
python -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -e . pytest
.venv/bin/pytest -q
```

运行 baseline：

```bash
.venv/bin/python scripts/run/run_baseline.py --config config/baseline.yaml
```

A 股如果要扩大股票池，不要继续只在 YAML 里手写两三个 `symbols`。可以直接给配置加一个股票列表文件：

```yaml
symbols_file: "cn_a_symbols_sample.txt"
```

文件格式是一行一个代码，支持空行和 `#` 注释，例如：

```text
600000.SH
000001.SZ
600519.SH
```

如果要在服务器上生成更大的 A 股股票池，不要手工整理代码列表。可以直接运行：

```bash
.venv/bin/python scripts/run/build_a_share_universe.py \
  --trade-date 2026-05-29 \
  --universe hs300 \
  --output config/cn_a_hs300_symbols.txt
```

或者：

```bash
.venv/bin/python scripts/run/build_a_share_universe.py \
  --trade-date 2026-05-29 \
  --universe zz500 \
  --output config/cn_a_zz500_symbols.txt
```

然后直接使用：

```bash
.venv/bin/python scripts/run/run_baseline.py --config config/a_share_baostock_hs300.yaml
```

如果你只想先把几百只 A 股日线缓存到磁盘，再单独训练回测，可以先跑：

```bash
.venv/bin/python scripts/run/run_a_share_baostock.py --config config/a_share_baostock_hs300.yaml
```

如果你要避免“拿 2026 年静态股票池回测 2021 年历史”这种生存者偏差，可以给配置增加逐日股票池：

```yaml
universe_membership_csv: "cn_a_zz500_membership_daily.csv"
```

最简单的过渡方案，是先把一个静态股票列表展开成逐日 `date,symbol`：

```bash
.venv/bin/python scripts/run/build_daily_universe_membership.py \
  --symbols-file config/cn_a_zz500_symbols.txt \
  --start-date 2021-01-01 \
  --end-date 2026-05-29 \
  --output config/cn_a_zz500_membership_daily.csv
```

然后可以直接跑一个“带逐日股票池过滤”的对照配置：

```bash
.venv/bin/python scripts/run/run_baseline.py --config config/a_share_baostock_zz500_membership.yaml
```

如果你已经确认要减少成份股历史变化带来的生存者偏差，不要继续只用“静态名单按日展开”。可以直接用 BaoStock 按历史交易日生成真实滚动 membership：

```bash
.venv/bin/python scripts/run/build_baostock_historical_membership.py \
  --universe zz500 \
  --start-date 2021-01-01 \
  --end-date 2026-05-29 \
  --output config/cn_a_zz500_membership_historical.csv
```

如果不是在 GPU 服务器上运行，需要把 `config/baseline.yaml` 里的 `data_dir` 和 `report_dir` 改成本地可写目录。

## 当前安全边界

当前不会做这些事：

1. 不连接真实股票账户。
2. 不保存券商 API key。
3. 不自动下单。
4. 不做实盘交易。

合理顺序应该是：

```text
离线数据验证 -> 严格回测 -> paper trading（模拟盘） -> 小权限实盘
```

真实账户接入必须等 paper trading、风控、日志、kill switch 都做好之后再考虑。

## 当前限制

1. Stooq 在服务器测试时返回 API key/captcha 提示。
2. Yahoo chart 在 GPU 服务器上返回 HTTP 403。
3. 当前 synthetic fallback 只用于验证工程链路。
4. 第一版 baseline 只有价格特征，还没有新闻/舆情/LLM 特征。
5. 本工程中的任何结果都不构成投资建议。

## License

MIT
