# 代码讲解（Code Walkthrough）

这份文档按文件解释代码。中文为主，关键英文术语保留在括号里，方便后续看英文资料。

如果你遇到不熟的概念，比如 `ret_1d`、`walk-forward`、`look-ahead leakage`、`AUC`、`log_loss`、`Parquet`、`DuckDB`、`滑点`，先看 [CONCEPTS.md](CONCEPTS.md)。

## `config/baseline.yaml`

这是第一版实验配置。配置文件本身已经写了大量中文注释，解释每个字段是什么、为什么先这么设。

```yaml
symbols:
  - AAPL.US
  - MSFT.US
  - NVDA.US
  - SPY.US
start_date: "2018-01-01"
end_date: "2026-05-29"
allow_synthetic_fallback: true
```

重要字段：

| 字段                      | 说明                  |
| ----------------------- | ------------------- |
| `symbols`               | 股票/ETF 列表           |
| `data_dir`              | 原始数据、特征、DuckDB 保存目录 |
| `report_dir`            | 预测结果和指标保存目录         |
| `train_window_days`     | 滚动训练窗口长度            |
| `test_window_days`      | 样本外测试窗口长度           |
| `probability_threshold` | long/flat 决策阈值      |
| `transaction_cost_bps`  | 仓位变化时的交易成本          |

补充解释：

- `train_window_days: 756` 约等于 3 年交易日，用过去 3 年训练。
- `test_window_days: 63` 约等于 1 个季度，训练完后预测未来 1 个季度。
- `probability_threshold: 0.55` 表示上涨概率至少 55% 才 long。
- `transaction_cost_bps: 5` 表示每次仓位变化扣 0.05% 成本。

## `src/quant_llm/config.py`

作用：加载 YAML 配置。

核心函数：

```python
config = load_config("config/baseline.yaml")
```

它会检查 YAML 顶层必须是 dict/mapping。如果配置文件格式不对，会直接报错。

## `src/quant_llm/data.py`

作用：加载行情数据。

主入口：

```python
prices = load_price_panel(
    symbols,
    start_date,
    end_date,
    data_dir,
    allow_synthetic_fallback=True,
)
```

执行逻辑：

1. 先检查 `data/raw/<symbol>.csv` 是否存在。
2. 如果缓存存在，直接读取缓存。
3. 如果没有缓存，尝试 Yahoo chart 接口。
4. 如果 Yahoo 失败且允许 fallback，就生成 deterministic synthetic data。
5. 返回统一格式：

```text
date, open, high, low, close, volume, symbol
```

这里的 synthetic data 是合成数据，只用于工程验证，不用于策略结论。

## `src/quant_llm/features.py`

作用：从价格生成特征和标签。

主入口：

```python
features = build_price_features(prices, horizon_days=1)
```

生成的特征：

```text
ret_1d          # 1 日收益
ret_5d          # 5 日收益
ret_20d         # 20 日收益
vol_20d         # 20 日波动率
ma_gap_10d      # 当前价格相对 10 日均线偏离
ma_gap_50d      # 当前价格相对 50 日均线偏离
range_1d        # 日内 high-low range
volume_z_20d    # 成交量 20 日 z-score
```

这些特征的金融直觉：

- 收益率特征看趋势或反转。
- 波动率特征看风险状态。
- 均线偏离看价格相对近期均衡的位置。
- 成交量 z-score 看是否有异常放量。

标签：

```text
future_ret = next close / current close - 1
target_up = future_ret > 0
```

滚动窗口前面的 warm-up 行会有缺失值，所以最后会 drop 掉。

## `src/quant_llm/modeling.py`

作用：训练模型并生成 walk-forward 预测。

主入口：

```python
predictions, fold_metrics = walk_forward_predict(features, walk_config, model_config)
```

walk-forward 的意义是避免明显的 look-ahead leakage：

```text
只用过去训练 -> 预测未来窗口 -> 再往前滚动
```

当前 fold metrics：

```text
accuracy
auc
log_loss
```

`walk_forward_predict` 的输出 `predictions` 是所有样本外窗口拼起来的预测记录。它相当于模拟“模型在历史上每个阶段真实运行时会给出的预测”。

模型优先使用 XGBoost。如果不可用，fallback 到 RandomForest。

## `src/quant_llm/backtest.py`

作用：把预测概率变成策略收益。

主入口：

```python
metrics = long_flat_backtest(predictions, threshold=0.55, transaction_cost_bps=5)
```

策略规则：

```text
prob_up >= threshold -> long
prob_up < threshold  -> cash
```

它不是最终策略，只是最小可审计 baseline，用来验证回测框架是否跑通。

例子：

```text
prob_up = 0.62, threshold = 0.55 -> long
future_ret = 0.01 -> 策略收益约 +1%，再扣交易成本

prob_up = 0.48, threshold = 0.55 -> flat
future_ret = 0.02 -> 没持仓，所以这天不赚这个上涨
```

## `scripts/run/run_baseline.py`

作用：端到端运行。

流程：

1. 读取 config。
2. 加载 prices。
3. 生成 features。
4. 训练 walk-forward 模型并输出 predictions。
5. 回测。
6. 保存 Parquet。
7. 保存 JSON metrics。
8. 创建 DuckDB views。

`duckdb_string_literal` 用于安全转义 DuckDB DDL 里的文件路径。

## Tests

`tests/test_features.py`：检查特征生成是否包含关键列和标签。

`tests/test_duckdb_literal.py`：检查 DuckDB 字符串路径转义。

`tests/test_text_features.py`：检查新闻文本事件抽取、每日文本特征聚合、和价格特征 join 是否正确。

## `src/quant_llm/text_features.py`

作用：把新闻/舆情文本变成模型能使用的表格特征。

当前第一版没有直接调用本地大模型，而是用 `RuleBasedTextExtractor` 模拟未来 LLM 的输出 schema。

这样做的原因：

1. 先跑通全链路，避免一开始就下载大模型浪费 GPU 费用。
2. 先固定 JSON schema，后续替换 LLM 时不影响下游训练和回测。
3. 方便写测试，保证文本特征聚合逻辑稳定。

流程：

```text
sample_news.csv
  -> extract_text_events
  -> text_events.parquet
  -> build_daily_text_features
  -> daily_text_features.parquet
  -> join_text_features
  -> training_features.parquet
```

当前文本特征：

```text
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

这些字段会和价格特征一起进入模型，影响最终 `prob_up`。
