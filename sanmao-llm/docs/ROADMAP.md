# 路线图（Roadmap）

## Phase 1：离线 Baseline

状态：已实现。

范围：

1. 行情加载器。
2. 公共数据源被阻断时的 synthetic fallback。
3. 价格技术特征。
4. walk-forward ML baseline。
5. 简单 long/flat 回测。
6. Parquet、DuckDB、JSON 输出。

## Phase 2：稳定历史行情源

用稳定数据源替换 synthetic fallback：

1. 付费历史行情。
2. 券商历史行情的只读接口。
3. 本地 CSV/Parquet 导入 pipeline。
4. 前复权/后复权/不复权的明确处理。
5. corporate actions（拆股、分红等）校验。

优先建议先做日线或分钟线的定时批处理，不急着做实时在线学习。实时系统更贵、更复杂，也更容易因为延迟、断线、重复下单出事故。

市场数据源选择见 [MARKET_DATA.md](MARKET_DATA.md)。

## Phase 2.5：股票池和回测框架做扎实

这部分不急着一次做完，但必须逐步补齐。否则即使模型输出看起来赚钱，也可能只是回测幻觉。

### 股票池要做扎实

当前只用了：

```text
AAPL.US
MSFT.US
NVDA.US
SPY.US
```

这只是工程验证股票池，不是正式研究股票池。

后续要补：

1. 扩展到更大股票池，例如 Nasdaq 100、S&P 500 或高流动性股票池。
2. 按行业、流动性、市值做分层。
3. 处理幸存者偏差：不能只看今天还活着的股票。
4. 处理成分股历史变化：例如过去某天是否属于指数。
5. 排除成交量太低、价格异常、长期停牌的标的。
6. 增加 benchmark：SPY buy-and-hold、等权股票池、行业 ETF。

### 回测框架要做扎实

当前回测只是最小 baseline：

```text
prob_up >= threshold -> long
prob_up < threshold -> flat
```

后续要补：

1. 真实下单时间：今天收盘后的信号只能用于下一交易日。
2. 更真实的交易成本：佣金、买卖价差、市场冲击。
3. 滑点模型：模拟实际成交价比理想价格更差。
4. 仓位管理：决定买多少，而不是只做 0/1。
5. 组合约束：单票上限、行业上限、总仓位上限。
6. 风控：最大日亏损、最大回撤、异常信号停机。
7. 参数防过拟合：不能为了历史好看反复调阈值。
8. 分阶段样本外验证：牛市、熊市、震荡市分开看。
9. 交易日志：每次信号要能解释原因、概率、特征和成本。
10. paper trading：真实账户前必须先模拟盘。

### 当前判断

这些都不是今天必须一次完成，但必须记录下来，后续一项项补齐。当前最急的是先跑通：

```text
真实行情 + 新闻/舆情文本特征 + 模型预测 + 回测
```

## Phase 3：LLM 文本特征

状态：第一版全链路已跑通，但当前使用规则抽取器模拟 LLM 输出，还没有下载/部署本地大模型。

加入新闻、公告、研报、社媒处理：

1. 原始文本 ingestion。
2. 实体识别和 ticker linking。
3. LLM JSON extraction schema。
4. embedding 去重和事件聚类。
5. 文本特征按时间和 symbol join 到市场特征表。

当前已实现：

1. `data_samples/news/sample_news.csv` 样例新闻。
2. `RuleBasedTextExtractor`，输出和未来 LLM 一致的 JSON schema。
3. `text_events.parquet`：逐条新闻事件。
4. `daily_text_features.parquet`：按 symbol/date 聚合后的文本特征。
5. `training_features.parquet`：价格特征 + 文本特征合并后的训练表。
6. baseline 使用 Tiingo 真实行情 + 文本特征完成训练和回测。
7. SEC EDGAR 免费公告源：已能抓取 8-K、10-Q、10-K 并接入文本特征 pipeline。

下一步：

1. 更好的新闻源质量后续再优化，例如 GDELT ticker linking、RSS、Finnhub free。
2. 当前优先把 `RuleBasedTextExtractor` 的输出替换成 Claude API（`AnthropicLLMExtractor`）真实抽取。
3. 增加一键 pipeline runner，把拉数据、生成文本特征、训练、回测串起来。
4. 对比“只有价格特征”和“价格 + SEC filings 特征”和“价格 + 新闻特征”的样本外表现。
5. 增加 LLM 输出校验，防止 JSON 字段缺失或乱填。

候选本地模型：

```text
Qwen3-32B-Instruct-AWQ
DeepSeek-R1-Distill-Qwen-32B
Qwen2.5-Coder-32B-Instruct-AWQ
```

模型选择和“为什么还需要传统 ML”的详细解释见 [MODEL_STRATEGY.md](MODEL_STRATEGY.md)。

## Phase 4：更严格的回测

需要增加：

1. slippage model（滑点模型）。
2. 更真实的下单时间。
3. portfolio construction（组合构建）。
4. 仓位限制。
5. 行业/单票集中度限制。
6. walk-forward hyperparameter control。
7. benchmark comparison。

## Phase 4.5：受控自动优化，而不是盲目自动调参

当前程序不会在回测不理想时自动修改模型参数。这是有意保守，因为直接让程序“调到历史收益最好”很容易过拟合。

后续要做自动优化，需要按下面方式做：

1. 增加 `scripts/run/run_search_all.sh`，专门跑候选参数和候选特征组合。
2. 增加独立 validation 区间，不能用最终 test 区间挑参数。
3. 对每个候选模型保存 `metrics.json`、`backtest_daily.csv`、参数配置和模型文件。
4. 自动筛选时同时看 Sharpe、max drawdown、turnover、exposure、稳定性，不只看 total return。
5. 每次运行都保存 `models/<strategy_id>/candidate_model.joblib`，方便复盘。
6. 只有通过门槛的候选模型，才覆盖 `models/<strategy_id>/latest_model.joblib`。
7. `models/<strategy_id>/latest_model.joblib` 继续代表当前配置训练出的最新可用模型，不等于“历史最优模型”。
8. paper trading 之前必须有模型版本、数据版本、特征版本和回测报告。

## Phase 5：Paper Trading

状态：第一版已开始实现。

离线证据足够后逐步做：

1. paper account 接入：第一版用 CSV 模拟账户，不接券商。
2. signal audit log：第一版输出 `paper_signals.csv`。
3. order audit log：第一版输出 `paper_orders.csv`。
4. portfolio snapshot：第一版输出 `paper_portfolio.csv`。
5. reconciliation（对账）：未完成。
6. kill switch：未完成。
7. 最大仓位和最大亏损限制：第一版只有 `max_symbol_weight`，还没有完整风控。

第一版 paper trading 建议使用“定时任务”：

```text
每天收盘后更新数据 -> 生成明日信号 -> 人工确认或模拟下单
```

不要一开始做全自动实时下单。

## Phase 6：小权限实盘

paper trading 稳定后才考虑：

1. 最小交易权限。
2. 小资金/小仓位。
3. 日亏损上限。
4. 人工确认模式。
5. 紧急关闭路径。

## Phase 6.5：A 股适配

目标：把 A 股作为独立市场适配，不污染美股 Alpaca paper 代码。

已完成：

1. 新增 `src/quant_llm/market_rules.py`。
2. 增加 `CHINA_A_RULES`：100 股一手、T+1、不允许小数股、不允许做空。
3. paper trading 股数生成已通过 market rules 取整。
4. 新增 QMT 环境检测骨架：`scripts/verify/check_qmt_env.py`。
5. 新增 A 股 QMT 预留配置：`config/a_share_qmt.yaml`。

待完成：

1. A 股行情数据源：Tushare / AkShare / BaoStock / QMT 数据。
2. A 股配置：`config/a_share_baseline.yaml`。
3. A 股回测规则：T+1、涨跌停、停牌、手续费、印花税。
4. A 股券商适配：QMT 或 PTrade。
5. A 股模拟盘对账。

详细说明见 [A_SHARE_ADAPTER_PLAN.md](A_SHARE_ADAPTER_PLAN.md)。

## 实盘前今晚优先清单

今晚可以推进到“paper account 工程闭环”，但不建议直接真实资金实盘。

已经完成或正在完成：

1. 离线研究链路：行情、SEC/Qwen 文本、特征、训练、回测、模型晋级。
2. 本地模拟盘：`reports/paper_trading/` 下生成信号、模拟订单、模拟持仓。
3. Alpaca paper adapter：把模拟盘订单转换成 Alpaca paper API 订单，默认只预览不提交。

仍然缺：

1. 你创建 Alpaca paper trading 账号，并提供 Paper API Key / Secret。
2. 服务器 `.env` 写入 `ALPACA_API_KEY_ID`、`ALPACA_API_SECRET_KEY`。
3. 先运行 `submit_alpaca_paper_orders.py` 的预览模式，确认订单方向和数量。
4. 再把 `broker.submit_orders` 改成 `true`，只提交到 Alpaca paper API。
5. 增加日亏损/最大回撤 kill switch。
6. 增加 broker positions 对账：本地 paper_portfolio 和 Alpaca positions 必须能核对。
7. 连续观察 paper trading 后，才考虑小权限真实账户。
