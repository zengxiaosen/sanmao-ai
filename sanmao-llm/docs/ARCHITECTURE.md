# 架构说明（Architecture）

## 目标

`sanmao-quant-llm` 是一个分阶段建设的量化研究系统。第一阶段先把离线研究闭环跑通：

```text
数据源（data source）
  -> 清洗后的 OHLCV 行情面板
  -> 特征表（feature table）
  -> walk-forward 机器学习预测
  -> long/flat 回测
  -> Parquet + DuckDB + JSON 报告
```

新闻、公告、舆情等 LLM 文本特征已经有第一版 pipeline：当前用规则抽取器模拟 LLM 输出，也可切换到 Claude API（`AnthropicLLMExtractor`）做真实抽取。

不熟悉术语时，先看 [CONCEPTS.md](CONCEPTS.md)。里面解释了特征、样本外测试、walk-forward、回测、Parquet、DuckDB、滑点和对账。

## 系统最终如何服务于智能买入/卖出

最终交易系统不应该只有一个模型。更合理的分层是：

```text
行情/新闻/公告/社媒
  -> 特征工程
  -> 预测模型：输出上涨概率、风险概率或预期收益
  -> 策略层：结合阈值、成本、仓位和风控决定目标仓位
  -> 市场规则层：A 股 T+1/100 股一手，美股小数股，港股 lot size
  -> 券商适配层：Alpaca / QMT / PTrade / 其他 broker
  -> 回测、模拟盘、对账和风控验证
  -> 小权限实盘
```

当前 baseline 已实现前三步中最基础的一部分，并且已经能把样例新闻文本特征合并进训练表：

```text
Tiingo 日线行情 + 样例新闻
  -> 价格特征 + 文本特征
  -> 预测下一交易日上涨概率
  -> long/flat 回测
```

后续真实 LLM 的作用是替换当前规则抽取器，增强“文本特征工程”，不是直接替代策略和风控。

LLM 字段和 `prob_up` 的关系见 [CONCEPTS.md](CONCEPTS.md#llm-结构化特征和预测概率是什么关系)。简短说：LLM JSON 会先变成表格特征，再和价格特征合并，最后由 ML 模型学习这些特征和未来涨跌之间的历史关系，并输出 `prob_up`。

## 数据流

### 1. 行情加载（Price Loading）

代码位置：`src/quant_llm/data.py`

加载器会先尝试从 Yahoo chart 接口获取日线 OHLCV 数据。部分服务器环境访问这个接口返回 HTTP 403，所以 baseline 配置中启用了 `allow_synthetic_fallback`。

synthetic fallback 是按 symbol 固定随机种子生成的合成行情。它用于可复现的工程 smoke test，不用于证明策略有效。

### 2. 特征工程（Feature Engineering）

代码位置：`src/quant_llm/features.py`

第一版特征故意保持简单：

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

这些特征的逐项解释见 [CONCEPTS.md](CONCEPTS.md#当前特征解释)。

标签（label）是：

```text
target_up = future_ret > 0
```

默认 `future_ret` 是下一交易日收益。

### 3. 建模（Modeling）

代码位置：`src/quant_llm/modeling.py`

建模使用 walk-forward splits：

1. 用历史窗口训练模型。
2. 预测下一个测试窗口。
3. 窗口向前滚动。
4. 拼接所有样本外预测（out-of-sample predictions）。

默认优先使用 XGBoost。如果 XGBoost 不可用，会 fallback 到 `RandomForestClassifier`。原因见 [CONCEPTS.md](CONCEPTS.md#为什么优先-xgboostfallback-到-randomforest)。

### 4. 回测（Backtest）

代码位置：`src/quant_llm/backtest.py`

当前策略非常简单：

```text
if prob_up >= threshold:
    下一期持有 long
else:
    空仓 cash
```

仓位变化时收取交易成本（transaction cost）。指标包括 total return、annual return、annual volatility、Sharpe、max drawdown、turnover、hit rate 和 exposure。这些指标的含义见 [CONCEPTS.md](CONCEPTS.md#回测指标解释)。

### 5. 存储（Storage）

代码位置：`scripts/run/run_baseline.py`

输出文件：

```text
data/<strategy_id>/features/prices.parquet
data/<strategy_id>/features/price_features.parquet
reports/<strategy_id>/predictions.parquet
reports/<strategy_id>/metrics.json
data/<strategy_id>/quant.duckdb
```

DuckDB 视图：

```sql
prices
price_features
predictions
```

## LLM / 新闻文本特征层

LLM 不应该直接输出“买/卖”。它应该把新闻、公告、研报、社媒转成结构化特征：

```json
{
  "tickers": ["AAPL"],
  "event_type": "earnings",
  "sentiment": -0.2,
  "confidence": 0.82,
  "impact_horizon": "1-5d",
  "risk_tags": ["margin_pressure"]
}
```

这些字段再按 `symbol + timestamp/date` join 到市场特征表里，交给 ML 模型学习。

更具体的数据流：

```text
新闻文本
  -> LLM JSON
  -> daily_text_features
  -> join price_features by symbol/date
  -> training_features
  -> model.predict_proba(...)
  -> prob_up
```

当前实现中，`RuleBasedTextExtractor` 暂时模拟这一步，输出同样 schema；也可切换到 `AnthropicLLMExtractor`（Claude API）做真实抽取。这样可以先跑通工程链路，需要真实抽取时只需配置 `ANTHROPIC_API_KEY`，无需 GPU。

## 多市场 / 多券商设计原则

以后可能同时研究美股、港股、A 股，但这三类市场不能把规则写死在同一段策略代码里。

本项目按下面边界拆分：

```text
模型层：
  输入特征，输出 prob_up / 预期收益 / 风险概率。
  不知道券商是谁，也不关心 A 股一手多少股。

策略层：
  把 prob_up 变成目标仓位，例如 long/flat、等权、最大仓位。

市场规则层：
  负责股数取整、T+1、是否允许小数股、是否允许做空、交易币种。
  代码位置：src/quant_llm/market_rules.py

券商适配层：
  负责把订单计划转换成券商 API 请求，并查询账户、订单、持仓。
  代码位置：src/quant_llm/brokers/
```

## 多市场数据、模型、报告如何防止互相覆盖

你的担心是对的：如果所有策略都写到同一个 `models/latest_model.joblib`，那 A 股跑一次就可能把美股模型覆盖掉，后续 paper trading 再加载就会乱。

现在项目强制按下面三个身份区分：

```text
market:
  市场，例如 US、CN_A、HK。

strategy_id:
  策略/实验 ID，例如 us_sec_qwen_xgboost_v1。

model_dir:
  该策略自己的模型目录，例如 models/us_sec_qwen_xgboost_v1/。
```

当前约定：

```text
美股 Qwen + SEC:
  config/sec_filings_qwen.yaml
  market: US
  strategy_id: us_sec_qwen_xgboost_v1
  data_dir:    data/us_sec_qwen_xgboost_v1/
  report_dir:  reports/us_sec_qwen_xgboost_v1/
  model_dir:   models/us_sec_qwen_xgboost_v1/

A 股 BaoStock:
  config/a_share_baostock.yaml
  market: CN_A
  strategy_id: cn_a_baostock_price_xgboost_v1
  data_dir:    data/cn_a_baostock_price_xgboost_v1/
  report_dir:  reports/cn_a_baostock_price_xgboost_v1/
  model_dir:   models/cn_a_baostock_price_xgboost_v1/

港股富途预留:
  config/hk_futu.yaml
  market: HK
  strategy_id: hk_futu_placeholder_v1
  data_dir:    data/hk_futu_placeholder_v1/
  report_dir:  reports/hk_futu_placeholder_v1/
  model_dir:   models/hk_futu_placeholder_v1/
```

也就是说，每个策略目录里才有自己的：

```text
candidate_model.joblib
candidate_model_metadata.json
latest_model.joblib
latest_model_metadata.json
```

程序层也做了兜底：`src/quant_llm/paths.py` 负责解析 `model_dir`。即使未来新增配置文件时忘了写 `model_dir`，代码也会自动落到：

```text
models/<strategy_id>/
```

如果连 `strategy_id` 也忘了写，就使用配置文件名兜底，例如：

```text
config/my_new_strategy.yaml -> models/my_new_strategy/
```

这样不会再默认写到共享的：

```text
models/latest_model.joblib
data/features/training_features.parquet
reports/metrics.json
```

### 行情 provider 以后怎么拆

当前 `src/quant_llm/data.py` 已经支持多个 provider，例如：

```text
tiingo      美股日线
yfinance    美股/港股等快速研究
baostock    A 股历史日线
synthetic   工程测试用假数据
```

短期为了快速打通链路，provider 还在一个文件里。随着 A 股、港股逻辑变复杂，应该逐步拆成更清晰的文件：

```text
src/quant_llm/data_sources/base.py
src/quant_llm/data_sources/us_tiingo.py
src/quant_llm/data_sources/a_share_baostock.py
src/quant_llm/data_sources/hk_futu.py
```

拆分原则：

```text
同一个 provider 只负责“拿数据并整理成统一 OHLCV 格式”；
不要在 provider 里写交易策略；
不要在 provider 里写券商下单；
不要在 provider 里写 A 股 T+1 或涨跌停回测逻辑。
```

### A 股 T+1 和涨跌停应该放在哪里

A 股特殊规则应该放在市场规则/回测/模拟盘层，而不是模型层。

后续要补的 A 股规则包括：

```text
T+1:
  当天买入的股票当天不能卖出。

涨跌停:
  涨停时不一定能买到；
  跌停时不一定能卖出。

100 股一手:
  买入数量必须按 100 股取整。

费用:
  佣金、印花税、过户费、滑点要单独建模。
```

当前已经有第一版市场规则：

```text
src/quant_llm/market_rules.py
```

已支持：

```text
US:
  小数股。

CN_A:
  100 股一手取整。
  标记 T+1。

HK:
  预留港股市场规则。
```

还没有做扎实的：

```text
A 股 T+1 在回测中的持仓锁定；
A 股涨跌停可成交性；
港股不同股票不同 lot size；
不同市场独立 benchmark；
不同市场独立风控阈值。
```

当前已实现：

```text
US:
  Alpaca paper trading
  支持小数股
  当前用于美股 paper broker 闭环

CN_A:
  已有 A 股市场规则对象
  买入按 100 股一手向下取整
  标记 T+1
  还没有接 QMT / PTrade

HK:
  预留港股市场规则对象
  后续需要按具体股票 lot size 细化
```

港股券商接入优先走富途牛牛 / Moomoo OpenAPI：

```text
Python SDK -> OpenD -> 富途服务器 -> 港股 paper/live
```

当前已新增：

```text
FutuConfig
FutuTradingClient 占位适配器
scripts/verify/check_futu_opend.py
config/hk_futu.yaml
```

现在只做 OpenD 环境检测，不 unlock trade，不下单。

## Broker 代码结构

券商代码不能再堆到一个大文件里。当前结构是：

```text
src/quant_llm/broker.py
  兼容导出层。旧脚本可以继续 from quant_llm.broker import ...

src/quant_llm/brokers/alpaca.py
  Alpaca Paper REST 客户端。

src/quant_llm/brokers/common.py
  broker-neutral 订单计划、提交前风控、paper ledger 对账。

src/quant_llm/brokers/qmt.py
  QMT/miniQMT 环境检测和占位适配器。

src/quant_llm/brokers/futu.py
  富途/Moomoo OpenD 环境检测和占位适配器。
```

后续新增 broker 时，规则是：

```text
1. 不把新券商逻辑写进 broker.py。
2. 新增 src/quant_llm/brokers/<broker_name>.py。
3. 只把稳定公共函数放进 brokers/common.py。
4. 每个 broker 独立测试文件：tests/test_broker_<broker_name>.py。
```

这样做的目的：

```text
同一个模型信号可以在不同市场规则下生成不同订单；
同一个策略可以接不同 broker；
接 A 股时不用改美股 Alpaca 代码；
接港股时也不用污染 A 股规则。
```
