# Pipeline 数据流说明

这份文档解释 `start_server_workflow.sh`、`run_sec_pipeline.sh`、`run_baseline.py` 之间到底怎么联动，以及文件写到哪里。

## 先说结论

脚本现在分成三个目录：

```text
scripts/env/      环境准备：装依赖、下载模型、开代理隧道
scripts/run/      正式运行：拉数据、生成特征、训练、回测、LLM 抽取
scripts/verify/   测试验证：检查行情、检查 Qwen、开机后一键验证
```

三个目录各自有总入口：

```text
scripts/env/setup_server_all.sh      新机器完整部署
scripts/run/run_all.sh               正式研究链路总入口
scripts/verify/verify_all.sh         验证当前机器是否正常
```

`scripts/verify/start_server_workflow.sh` 不是下载大模型的脚本。

它做的是“服务器已经部署好之后的一键启动/验证”：

```text
1. 跑 pytest，确认量化代码没坏。
2. 跑 run_sec_pipeline.sh，执行 SEC + Tiingo baseline。
3. 跑 Qwen smoke test，确认本地大模型还能加载并输出 JSON。
4. 用 Qwen 对 sample_news.csv 抽 3 条样例，确认 extractor 可用。
```

下载大模型在这里：

```text
scripts/env/setup_server_all.sh
scripts/env/download_llm_model.sh
```

当前模型目录：

```text
/root/autodl-tmp/models/qwen3-8b-awq
```

当前 Hugging Face 缓存目录：

```text
/root/autodl-tmp/hf
```

当前 LLM 环境目录：

```text
/root/autodl-tmp/llm-env
```

## start_server_workflow.sh 写哪些文件

它会间接或直接生成：

```text
data/<strategy_id>/news/sec_filings.csv
data/<strategy_id>/features/prices.parquet
data/<strategy_id>/features/price_features.parquet
data/<strategy_id>/features/text_events.parquet
data/<strategy_id>/features/daily_text_features.parquet
data/<strategy_id>/features/training_features.parquet
reports/<strategy_id>/predictions.parquet
reports/<strategy_id>/metrics.json
data/<strategy_id>/quant.duckdb
data/llm_smoke_qwen/news/qwen_sample_events.csv
```

其中：

| 文件 | 来源 | 用途 |
|---|---|---|
| `data/<strategy_id>/news/sec_filings.csv` | `fetch_sec_filings.py` | SEC 原始公告/财报事件文本 |
| `data/<strategy_id>/features/prices.parquet` | `run_baseline.py` | Tiingo 行情 |
| `data/<strategy_id>/features/price_features.parquet` | `run_baseline.py` | 价格特征 |
| `data/<strategy_id>/features/text_events.parquet` | `run_baseline.py` | 规则抽取器生成的逐条文本事件 |
| `data/<strategy_id>/features/daily_text_features.parquet` | `run_baseline.py` | 按 date+symbol 聚合后的文本特征 |
| `data/<strategy_id>/features/training_features.parquet` | `run_baseline.py` | 价格特征 + 文本特征拼接后的最终训练表 |
| `reports/<strategy_id>/predictions.parquet` | `run_baseline.py` | walk-forward 预测结果，包含 `prob_up` |
| `reports/<strategy_id>/metrics.json` | `run_baseline.py` | 模型指标和回测指标 |
| `data/<strategy_id>/quant.duckdb` | `run_baseline.py` | DuckDB view，方便 SQL 查询 parquet |
| `data/llm_smoke_qwen/news/qwen_sample_events.csv` | `extract_news_with_llm.py` | Qwen 小样本抽取结果，只用于验证 |

## run_sec_pipeline.sh 和 run_baseline.py 怎么联动

它们不是共同写数据库同一张表。

它们通过“文件路径 + YAML 配置”联动。

流程是：

```text
run_sec_pipeline.sh
  -> fetch_sec_filings.py
      -> 写 data/<strategy_id>/news/sec_filings.csv

run_sec_pipeline.sh
  -> run_baseline.py --config config/sec_filings_baseline.yaml
      -> 读取 config/sec_filings_baseline.yaml
      -> 看到 text_features.news_csv = data/<strategy_id>/news/sec_filings.csv
      -> 读取 data/<strategy_id>/news/sec_filings.csv
      -> 生成文本特征
      -> 和价格特征 merge
      -> 写 training_features.parquet
      -> 写 DuckDB views
```

关键配置在：

```yaml
text_features:
  enabled: true
  news_csv: "/root/autodl-tmp/sanmao-quant-llm/data/us_sec_rule_text_xgboost_v1/news/sec_filings.csv"
```

也就是说：

```text
fetch_sec_filings.py 负责写 CSV
run_baseline.py 负责读 CSV
config/sec_filings_baseline.yaml 负责告诉 run_baseline.py 读哪个 CSV
```

## 特征是怎么拼接的

不是“共同写数据库同一个表不同列”。

实际是在 Python/pandas 里 merge：

```text
price_features
  date + symbol + ret_1d + ret_5d + vol_20d + ...

daily_text_features
  date + symbol + llm_news_count + llm_mean_sentiment + risk_* + ...

join_text_features(price_features, daily_text_features)
  -> 按 date + symbol left merge
  -> 得到 training_features
```

最终写到：

```text
data/<strategy_id>/features/training_features.parquet
```

这个文件才是模型训练输入。

## DuckDB 在这里做什么

DuckDB 当前不是主写入数据库，也不是多脚本共同追加列的地方。

`run_baseline.py` 只是创建 view：

```sql
CREATE OR REPLACE VIEW training_features AS
SELECT * FROM read_parquet('data/<strategy_id>/features/training_features.parquet')
```

所以 DuckDB 的作用是：

```text
方便用 SQL 查询 parquet 文件
```

不是：

```text
多个脚本同时往同一张物理表写不同列
```

## Qwen 当前是否参与主回测

现在有两条链路：

### 旧链路：规则抽取器 baseline

```bash
bash scripts/run/run_sec_pipeline.sh
```

这条链路使用：

```text
SEC filings 原始文本
-> RuleBasedTextExtractor
-> text_events
-> daily_text_features
-> training_features
```

### 新链路：Qwen LLM 全链路

```bash
bash scripts/run/run_all.sh
```

这条链路使用：

```text
SEC filings 原始文本
-> Qwen extractor
-> data/us_sec_qwen_xgboost_v1/news/sec_filings_qwen_events.csv
-> run_baseline.py 读取 events_csv
-> daily_text_features
-> training_features
-> walk-forward 训练/预测
-> 回测
```

`run_all.sh` 会自动检查：

```text
data/us_sec_qwen_xgboost_v1/news/sec_filings_qwen_events.csv 是否存在
```

如果不存在，它会自动调用：

```text
scripts/run/extract_news_with_llm.py
```

所以不需要你手动先跑 LLM 抽取。

## 训练、测试、预测、和真实结果比较在哪里

核心文件：

```text
scripts/run/run_baseline.py
src/quant_llm/modeling.py
src/quant_llm/backtest.py
```

分工：

```text
run_baseline.py
  负责读取配置、加载行情、加载文本特征、拼 training_features、调用训练/回测函数。

src/quant_llm/modeling.py
  负责 walk-forward：
    用训练窗口 train_window_days 训练模型
    用未来 test_window_days 做样本外预测
    预测输出 prob_up

src/quant_llm/backtest.py
  负责把 prob_up 变成 long/flat 仓位
  并用真实 forward_return 计算策略收益和指标
```

输出位置：

```text
data/<strategy_id>/features/training_features.parquet   最终训练表
reports/<strategy_id>/predictions.parquet               每个样本的 prob_up 和真实 forward_return
reports/<strategy_id>/metrics.json                      AUC/log_loss/backtest 等指标
reports/<strategy_id>/backtest_daily.csv                每日策略收益、资金曲线、回撤
reports/<strategy_id>/backtest_positions.parquet        每只股票每天的 position/strategy_ret
reports/<strategy_id>/latest_signals.csv                最新一天的 long/flat 信号
models/<strategy_id>/candidate_model.joblib             本次运行训练出的候选模型
models/<strategy_id>/candidate_model_metadata.json      候选模型元信息：特征列、训练区间、阈值、晋级原因等
models/<strategy_id>/latest_model.joblib                只有通过 model_promotion 门槛才覆盖的最新可用模型
models/<strategy_id>/latest_model_metadata.json         最新可用模型的元信息
```

`<strategy_id>` 来自 YAML 配置。例如：

```text
config/sec_filings_qwen.yaml:
  strategy_id: us_sec_qwen_xgboost_v1
  model_dir: models/us_sec_qwen_xgboost_v1/

config/a_share_baostock.yaml:
  strategy_id: cn_a_baostock_price_xgboost_v1
  model_dir: models/cn_a_baostock_price_xgboost_v1/
```

这点很重要：美股、A 股、港股的模型文件不会共用一个 `latest_model.joblib`。

## 回测的作用是什么

回测不是实盘，也不是模拟盘。

它的作用是回答：

```text
如果过去按这个模型和规则交易，大概会发生什么？
```

回测会用样本外预测 `prob_up` 和真实发生的 `future_ret` 比较，计算：

```text
total_return
annual_return
sharpe
max_drawdown
hit_rate_when_in_market
exposure
```

你要直观看收益，看：

```text
reports/backtest_daily.csv
```

里面：

```text
strategy_ret  当天策略收益
equity        从 1.0 开始累计的资金曲线
drawdown      当前回撤
```

也可以运行：

```bash
.venv/bin/python scripts/verify/show_report.py
```

## 回测之后会更新模型吗

严格说：

```text
回测本身不会“在线更新模型”。
```

当前 pipeline 在回测完成后，会额外做一步：

```text
用全部已有 training_features 重新训练一个 candidate_model
保存到 models/<strategy_id>/candidate_model.joblib
```

这一步在：

```text
scripts/run/run_baseline.py
  -> fit_final_model(...)
  -> models/<strategy_id>/candidate_model.joblib
  -> 如果 model_promotion 通过，再覆盖 models/<strategy_id>/latest_model.joblib
```

所以当前链路分成两件事：

```text
1. walk-forward 回测：
   在历史上反复“过去训练 -> 未来预测”，评估这个方法是否靠谱。

2. candidate_model 训练：
   回测跑完后，用当前能拿到的全部 training_features 重新训练一个模型，
   保存成候选模型。
```

为什么要重新训练一次？

```text
walk-forward 里不是一个模型，而是一串临时模型：
第 1 个模型：只看第 1 段训练窗口
第 2 个模型：只看第 2 段训练窗口
第 3 个模型：只看第 3 段训练窗口
...
```

这些临时模型的目的只是评估“过去如果这么做会怎样”，不适合作为后续模拟盘唯一加载的模型。

如果回测通过基本门槛，就需要用同一套参数、同一套特征、全部已有训练样本再训练出一个明确的模型文件：

```text
models/<strategy_id>/candidate_model.joblib
```

然后再根据 `model_promotion` 决定是否覆盖：

```text
models/<strategy_id>/latest_model.joblib
```

如果回测不理想：

```text
candidate_model 仍然保存，方便复盘；
latest_model 不会被覆盖；
不会自动调参数；
不会自动进入模拟盘或实盘。
```

## 如果回测不理想，会自动优化模型吗

当前不会自动优化。

这是故意保守，不是忘了做。原因是：如果程序看到回测不好，就自动反复调参数、调阈值、加特征，直到历史收益好看，很容易产生过拟合。

过拟合的意思是：

```text
模型把过去这段历史“背熟了”，回测很好看；
但一到未来真实行情，表现可能明显变差。
```

所以现在的正确顺序是：

```text
先固定一套简单规则 -> 跑 walk-forward -> 记录表现 -> 人工/程序提出候选改进
-> 用更严格的样本外验证检查 -> 通过后才替换当前模型配置
```

后面可以做“自动自适应优化”，但必须加保护：

```text
1. 参数搜索不能直接用最终回测区间调到最好。
2. 要把数据分成 train / validation / final test，或者做 nested walk-forward。
3. 每次候选模型都要和 benchmark 比较，例如 SPY buy-and-hold。
4. 不能只看 total return，还要看 max drawdown、Sharpe、turnover、稳定性。
5. 只有通过验证的配置，才允许保存成 production candidate。
```

当前会保存的模型：

```text
models/<strategy_id>/candidate_model.joblib
```

如果回测通过配置门槛，才会同时覆盖：

```text
models/<strategy_id>/latest_model.joblib
```

它们都不是“自动优化后的最优模型”。当前只是用固定配置训练出来的候选/最新模型。

## 那回测的意义在哪里

回测的意义不是让程序立刻自动修模型，而是给我们一个工程化的评估仪表盘：

```text
1. 看模型方向有没有一点统计边际。
2. 看加入 LLM 文本特征后有没有改善。
3. 看最大回撤是否超过可接受范围。
4. 看换手率是否太高，交易成本是否会吃掉收益。
5. 看不同时间段是否稳定，还是只在某一段行情里有效。
6. 给 paper trading 前提供最低限度证据。
```

如果回测差，下一步不是直接实盘，也不是让程序乱调，而是进入研究迭代：

```text
改股票池 / 改特征 / 改标签 / 改模型 / 改风控 / 改交易成本假设
-> 重新跑 walk-forward
-> 比较 reports/<strategy_id>/metrics.json 和 reports/<strategy_id>/backtest_daily.csv
```

## 当前回测时间窗口多长

主链路配置在：

```text
config/sec_filings_qwen.yaml
```

当前设置是：

```text
start_date: 2021-01-01
end_date:   2026-05-29
```

也就是本次实验使用约 5 年多的历史日线数据。

walk-forward 设置是：

```text
train_window_days: 756   约 3 年交易日
test_window_days:  63    约 1 个季度交易日
```

直观例子：

```text
第 1 轮：用前约 3 年训练 -> 预测接下来约 1 个季度
第 2 轮：窗口向前滚动 -> 再预测下一个季度
第 3 轮：继续滚动
...
```

最后把所有季度的样本外预测拼起来，再做回测。

这里的“拼起来”不是把模型拼起来，也不是把上一轮的模型参数传给下一轮。

它拼的是每一轮对未来测试区间产生的预测记录：

```text
第 1 轮预测 2024-Q1 -> 得到 2024-Q1 每天每只股票的 prob_up
第 2 轮预测 2024-Q2 -> 得到 2024-Q2 每天每只股票的 prob_up
第 3 轮预测 2024-Q3 -> 得到 2024-Q3 每天每只股票的 prob_up

把这些预测记录按日期接起来：
2024-Q1 预测 + 2024-Q2 预测 + 2024-Q3 预测 + ...
-> reports/predictions.parquet
```

然后回测读取 `reports/predictions.parquet`：

```text
prob_up >= probability_threshold -> long
prob_up <  probability_threshold -> flat
```

再用真实发生的 `future_ret` 计算这一天如果持仓会赚/亏多少，最终汇总成：

```text
reports/backtest_daily.csv
reports/<strategy_id>/metrics.json
```

```text
scripts/run/run_baseline.py
```

调用：

```text
fit_final_model(...)
joblib.dump(candidate_model, models/<strategy_id>/candidate_model.joblib)
```

所以现在有两个概念：

```text
walk-forward 临时模型：只用于历史回测评估，不保存。
candidate_model.joblib：回测完成后用全部已有数据训练出来的候选模型。
latest_model.joblib：只有 candidate_model 通过 model_promotion 门槛才覆盖，给后续模拟盘/应用加载。
这两个文件都在 `models/<strategy_id>/` 下面，不同市场/策略不会互相覆盖。
```

## 模拟盘下一步要做什么

现在还没有接券商，也没有 paper trading 引擎。

第一版已经新增：

```text
scripts/run/run_paper_trading.py
scripts/run/run_paper_all.sh
src/quant_llm/paper_trading.py
```

它们要做：

```text
1. 复用 run_all.sh 已经生成的 training_features.parquet。
2. 读取 latest_model_metadata.json，拿到训练时使用的 feature columns。
3. 加载 models/<strategy_id>/latest_model.joblib。注意：只有通过 model_promotion 门槛的候选模型才会晋级到这里。
4. 对最新日期的每只股票输出 prob_up 和 long/flat 建议。
5. 按等权目标仓位写入 paper account ledger，不真实下单。
```

运行：

```bash
bash scripts/run/run_paper_all.sh
```

输出：

```text
reports/<strategy_id>/paper_trading/paper_signals.csv     最新模拟盘信号
reports/<strategy_id>/paper_trading/paper_orders.csv      模拟订单流水
reports/<strategy_id>/paper_trading/paper_portfolio.csv   模拟持仓快照
reports/<strategy_id>/paper_trading/paper_summary.json    最新模拟账户摘要
```

如果要接券商 paper account，当前新增 Alpaca paper adapter：

```bash
.venv/bin/python scripts/run/submit_alpaca_paper_orders.py --config config/sec_filings_qwen.yaml
```

默认只生成预览，不提交订单：

```text
reports/<strategy_id>/paper_trading/broker_order_preview.csv
```

如果要提交到 Alpaca paper account，建议用命令行显式开关：

```bash
.venv/bin/python scripts/run/submit_alpaca_paper_orders.py \
  --config config/sec_filings_qwen.yaml \
  --submit-orders
```

脚本会用 `run_id` 做防重复检查。同一个模拟盘 `run_id` 如果已经提交过，会拒绝再次提交，避免重复买入/卖出。

提交后查看 Alpaca paper 账户、最近订单和持仓：

```bash
.venv/bin/python scripts/verify/check_alpaca_paper.py --config config/sec_filings_qwen.yaml
```

这个脚本还会输出并保存对账结果：

```text
reports/<strategy_id>/paper_trading/broker_reconciliation.csv
```

对账会比较：

```text
本地 paper_portfolio.csv 认为应该持有多少股
Alpaca paper positions 实际持有多少股
```

如果订单还只是 `accepted`、没有 `filled`，Alpaca positions 可能还是空的，这时对账会显示差异，属于未成交订单的正常状态。

要真正提交到 Alpaca paper API，需要：

```text
1. 你在 Alpaca 后台创建 Paper Trading API Key / Secret。
2. 服务器 .env 写入 ALPACA_API_KEY_ID 和 ALPACA_API_SECRET_KEY。
3. config/sec_filings_qwen.yaml 里 broker.submit_orders 改为 true。
4. base_url 保持 https://paper-api.alpaca.markets。
```

当前代码默认拒绝非 paper base_url，避免误接真实账户。

只有 paper trading 稳定后，才考虑小权限实盘。
