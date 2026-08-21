# 核心概念解释（Concepts）

这份文档解释 `sanmao-quant-llm` 里出现的量化、机器学习和工程概念。目标是让你能看懂代码为什么这么写，以及它最终如何服务于“智能买入/卖出”。

## 这个系统最终在预测什么

当前 baseline 预测的是：

```text
下一交易日 close 是否比今天 close 更高
```

代码里的变量：

```text
future_ret = next_close / current_close - 1
target_up = future_ret > 0
prob_up = 模型预测 target_up 为 1 的概率
```

举例：

| 今天 close | 明天 close | future_ret | target_up |
|---:|---:|---:|---:|
| 100 | 103 | 3% | 1，上涨 |
| 100 | 98 | -2% | 0，下跌 |

模型不是直接说“买入/卖出”，而是输出一个概率：

```text
prob_up = 0.62
```

意思是：模型认为下一交易日上涨概率约为 62%。

然后策略规则再把概率转换成交易动作：

```text
prob_up >= 0.55 -> long，也就是买入/持有
prob_up < 0.55  -> flat，也就是空仓
```

这就是“预测模型”和“交易策略”的分工：

```text
模型负责预测概率
策略负责根据概率、成本和风控决定买不买
```

## 为什么 LLM 不直接输出买/卖

你认同的方向是对的：LLM 更适合把新闻、公告、研报、社媒变成结构化特征，而不是直接喊单。

推荐流程：

```text
新闻/公告/社媒
  -> LLM 提取结构化特征
  -> 和市场数据拼接
  -> XGBoost/LightGBM/PyTorch 学习
  -> 回测验证
  -> 模拟盘
  -> 小权限实盘
```

LLM 输出示例：

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

这些字段会变成模型特征，而不是直接变成订单。

## LLM 结构化特征和预测概率是什么关系

你问的这个问题很关键：

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

这些字段本身不是 `prob_up`。它们只是“输入特征”（features）。模型会把它们和价格特征一起输入，然后输出上涨概率 `prob_up`。

完整关系是：

```text
价格特征 + LLM 文本特征
        -> 机器学习模型
        -> prob_up：未来上涨概率
        -> 策略阈值 + 风控
        -> long / flat / 后续更多动作
```

### 第一步：LLM 把文本变成结构化字段

假设有一条新闻：

```text
Apple reported earnings above expectations, but management warned that gross margin may be pressured next quarter.
```

LLM 不直接说“买 AAPL”或“卖 AAPL”，而是提取成结构化信息：

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

含义：

| 字段 | 含义 |
|---|---|
| `tickers` | 这条新闻影响哪些股票 |
| `event_type` | 事件类型，这里是财报 |
| `sentiment` | LLM 判断的文本情绪，-1 到 1，负数偏利空，正数偏利好 |
| `confidence` | LLM 对自己抽取结果的置信度 |
| `impact_horizon` | 这条新闻可能影响多长时间 |
| `risk_tags` | 风险标签，这里是毛利率压力 |

### 第二步：把 JSON 变成模型能吃的表格特征

机器学习模型不能直接吃原始 JSON，需要转成表格列。

例如可以变成：

| date | symbol | event_earnings | llm_sentiment | llm_confidence | horizon_1_5d | risk_margin_pressure |
|---|---|---:|---:|---:|---:|---:|
| 2026-05-30 | AAPL | 1 | -0.2 | 0.82 | 1 | 1 |

解释：

```text
event_earnings = 1              表示当天有 earnings 事件
llm_sentiment = -0.2            表示文本偏轻微利空
llm_confidence = 0.82           表示抽取可信度较高
horizon_1_5d = 1                表示影响期限是 1-5 天
risk_margin_pressure = 1        表示出现毛利率压力风险
```

然后它会和价格特征拼在同一行：

| date | symbol | ret_1d | ret_5d | vol_20d | ma_gap_10d | event_earnings | llm_sentiment | risk_margin_pressure | target_up |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-05-30 | AAPL | 0.01 | 0.04 | 0.018 | 0.03 | 1 | -0.2 | 1 | ? |

训练阶段，`target_up` 是后来真实发生的涨跌。预测阶段，`target_up` 不知道，所以模型输出 `prob_up`。

### 第三步：模型从历史中学习这些字段和未来涨跌的关系

训练时，模型会看到很多历史样本：

| 情况 | 后续表现 |
|---|---|
| 财报超预期 + 情绪正 + 无风险标签 | 后面 1-5 天经常上涨 |
| 财报超预期 + 情绪负 + margin_pressure | 后面经常震荡或下跌 |
| 政策利好 + 高置信度 + 行业共振 | 后面上涨概率提高 |
| 负面诉讼 + 高置信度 + 高成交量 | 后面下跌风险提高 |

模型学到的不是一句固定规则，而是大量历史样本中的统计关系。

也就是说：

```text
LLM 负责把文本变成可计算字段
ML 模型负责学习这些字段和未来收益之间的历史关系
```

### 第四步：预测阶段输出 `prob_up`

假设今天 AAPL 的输入特征是：

```text
ret_5d = 0.04
vol_20d = 0.018
ma_gap_10d = 0.03
event_earnings = 1
llm_sentiment = -0.2
risk_margin_pressure = 1
```

模型综合价格特征和文本特征后，可能输出：

```text
prob_up = 0.47
```

这表示模型认为下一交易日上涨概率只有 47%。如果阈值是 0.55：

```text
0.47 < 0.55 -> flat，不买/空仓
```

另一种情况：

```text
ret_5d = 0.02
vol_20d = 0.014
event_earnings = 1
llm_sentiment = 0.7
risk_margin_pressure = 0
```

模型可能输出：

```text
prob_up = 0.63
```

如果阈值是 0.55：

```text
0.63 >= 0.55 -> long，买入/持有
```

### 为什么 `sentiment=-0.2` 不等于上涨概率下降 20%

`sentiment=-0.2` 只是一个输入字段，不是最终结论。

它对 `prob_up` 的影响取决于历史数据里学到的关系。

例：

```text
同样 sentiment=-0.2
如果公司本身趋势很强、财报超预期、市场环境好，prob_up 可能仍然高
如果公司趋势弱、成交量异常、风险标签多，prob_up 可能更低
```

所以不要把某一个 LLM 字段单独理解成交易信号。模型会综合所有字段。

### `confidence` 怎么用

`confidence` 可以有几种用法：

1. 作为模型输入特征：让模型学习“高置信度新闻是否更有预测力”。
2. 作为过滤条件：置信度太低的 LLM 抽取结果不进入特征库。
3. 作为权重：同一天多条新闻聚合时，高置信度新闻权重更高。

例：

```text
weighted_sentiment = sentiment * confidence
```

如果：

```text
sentiment = -0.2
confidence = 0.82
weighted_sentiment = -0.164
```

### LLM 是怎么评估 `sentiment` 和 `confidence` 的

LLM 不是像行情模型那样从历史价格里“训练出一个概率”。在 extractor 这一步，它做的是语言理解和结构化判断。

我们会给 LLM 一个明确任务：

```text
阅读这条新闻/公告
只输出 JSON
判断事件类型、情绪、置信度、影响期限、风险标签
```

其中：

```text
sentiment = 这条文本对股票未来表现的方向性语气
confidence = LLM 对自己这次结构化抽取是否可靠的主观置信度
```

更准确地说，`confidence` 评估的是：

```text
这条文本是否足够清楚，让 LLM 能可靠地提取 event_type、sentiment、impact_horizon、risk_tags
```

它不是：

```text
这只股票上涨的概率
```

我们会在 prompt 里要求 LLM 按下面的尺度打分：

| confidence 区间 | 含义 | 典型文本 |
|---:|---|---|
| 0.85 - 0.95 | 很清楚，文本明确提到公司、事件、方向和风险 | “AAPL beat earnings and raised guidance” |
| 0.55 - 0.75 | 有相关信息，但好坏混合、语气不强或部分信息需要推断 | “beat earnings, but margins may be pressured” |
| 0.20 - 0.50 | 关联较弱、不确定、影响方向模糊 | “analysts discussed Apple before an event” |

所以 `confidence=0.82` 的意思是：

```text
LLM 认为“这条新闻确实和 AAPL 财报/毛利率压力相关，我对这个结构化抽取比较有把握”
```

而不是：

```text
AAPL 有 82% 概率上涨
```

举例：

```text
Apple beat earnings expectations and raised guidance.
```

LLM 可能输出：

```json
{
  "event_type": "earnings",
  "sentiment": 0.7,
  "confidence": 0.88,
  "impact_horizon": "1-5d",
  "risk_tags": []
}
```

原因：

```text
beat earnings = 财报超预期，偏利好
raised guidance = 上调指引，偏利好
文本含义明确，所以 confidence 高
```

再看一个例子：

```text
Apple beat earnings expectations, but management warned gross margin may be pressured next quarter.
```

LLM 可能输出：

```json
{
  "event_type": "earnings",
  "sentiment": -0.2,
  "confidence": 0.82,
  "impact_horizon": "1-5d",
  "risk_tags": ["margin_pressure"]
}
```

原因：

```text
beat earnings = 利好
margin may be pressured = 利空
好坏混合，所以 sentiment 接近中性但略负
风险表达清楚，所以 confidence 仍然较高
```

再看不明确文本：

```text
Apple shares were discussed by several analysts ahead of a product event.
```

LLM 可能输出：

```json
{
  "event_type": "product",
  "sentiment": 0.1,
  "confidence": 0.55,
  "impact_horizon": "1-5d",
  "risk_tags": []
}
```

原因：

```text
没有明确利好/利空
只是讨论和预期
所以 sentiment 接近 0，confidence 也较低
```

重要：`confidence` 不是“上涨概率”。

```text
confidence = LLM 对文本抽取结果的把握
prob_up = ML 模型根据所有特征预测未来上涨的概率
```

二者关系：

```text
LLM confidence 高，只说明“这条文本特征可信”
不代表“股票一定上涨”
```

### LLM 的置信度为什么不是严格数学概率

这里要分清两个概念：

```text
LLM confidence：语言抽取质量分
ML prob_up：交易预测概率
```

`LLM confidence` 更像“标注员对自己标注的把握”。比如一个人读新闻后说：

```text
我很确定这是一条财报新闻，而且提到了毛利率压力，所以 confidence 较高。
```

这不是在说：

```text
我很确定股价会涨。
```

真正和“涨跌概率”有关的是后面的机器学习模型输出 `prob_up`。它会把历史上的很多样本拿来训练：

```text
价格特征
+ LLM sentiment
+ LLM confidence
+ event_type
+ risk_tags
-> 学习这些组合之后，未来上涨/下跌的统计结果
-> 输出 prob_up
```

### confidence 在代码里怎么影响策略

当前代码里有一个每日聚合字段：

```text
llm_weighted_sentiment = sentiment * confidence
```

例子：

| 新闻 | sentiment | confidence | weighted_sentiment |
|---|---:|---:|---:|
| 明确利好 | 0.80 | 0.90 | 0.72 |
| 模糊利好 | 0.80 | 0.35 | 0.28 |
| 明确利空 | -0.60 | 0.90 | -0.54 |
| 模糊利空 | -0.60 | 0.35 | -0.21 |

这样做的直觉是：

```text
同样是利好/利空，文本越清楚、抽取越可靠，权重越大。
文本越模糊，权重越小，避免噪声新闻过度影响模型。
```

但注意：即使 `weighted_sentiment=-0.54`，也不等于马上卖出。它只是进入模型的一列特征。最终仍然要看模型输出的 `prob_up` 和策略规则。

### 工程上如何防止 LLM 乱给 confidence

LLM 可能输出不合理内容，比如：

```json
{
  "event_type": "rumor",
  "sentiment": 2.4,
  "confidence": -0.3,
  "impact_horizon": "next decade"
}
```

这些值不能直接进模型。当前代码在 `src/quant_llm/llm_extractor.py` 里做了基础防护：

```text
sentiment 裁剪到 -1 到 1
confidence 裁剪到 0 到 1
未知 event_type 归为 other
未知 impact_horizon 归为 1-5d
```

后续还要继续加强：

```text
1. JSON schema validation：严格校验字段类型。
2. ticker linking：确认新闻真的对应这只股票。
3. source quality：给不同新闻源不同可信度。
4. duplicate removal：去掉重复转载新闻。
5. human audit sample：抽样人工检查 LLM 标注质量。
```

### 为什么还要校验 LLM 输出

LLM 可能犯错：

1. 输出不是 JSON。
2. `sentiment` 超出 -1 到 1。
3. 把无关新闻错配到股票。
4. 把“苹果水果”当成 Apple 公司。
5. 置信度过高但理由不足。

所以后续要加：

```text
JSON schema 校验
字段范围裁剪
ticker linking
来源过滤
低 confidence 过滤
人工抽样复核
```

### 多条新闻怎么聚合

同一只股票同一天可能有很多条新闻。不能直接一条新闻一行，否则会和价格数据重复错位。

常见做法是按 `symbol + date` 聚合：

```text
llm_news_count
llm_mean_sentiment
llm_min_sentiment
llm_max_sentiment
llm_weighted_sentiment
event_earnings_count
risk_margin_pressure_count
```

例：

| date | symbol | llm_news_count | llm_mean_sentiment | risk_margin_pressure_count |
|---|---|---:|---:|---:|
| 2026-05-30 | AAPL | 8 | -0.15 | 3 |

然后这行再 join 到当天的价格特征。

### 当前代码做到哪一步

当前代码只实现了价格特征：

```text
ret_1d, ret_5d, ret_20d, vol_20d, ma_gap_10d, ma_gap_50d, range_1d, volume_z_20d
```

还没有实现 LLM 文本特征入库、聚合和 join。

下一阶段应该新增：

```text
raw_texts table
llm_events table
daily_text_features table
price_features + daily_text_features -> training_features
```

也就是：

```text
新闻文本 -> LLM JSON -> 每日文本特征 -> 和价格特征合并 -> 训练模型 -> prob_up
```

## 当前特征解释

### `ret_1d`

1 日收益率。

```text
ret_1d = 今天 close / 昨天 close - 1
```

例：昨天 100，今天 102：

```text
ret_1d = 102 / 100 - 1 = 2%
```

它反映短期动量或反转。

### `ret_5d`

5 日收益率。

```text
ret_5d = 今天 close / 5 个交易日前 close - 1
```

它反映一周级别趋势。

### `ret_20d`

20 日收益率，近似一个月收益。

它反映月度趋势。如果 `ret_20d` 很高，可能说明强趋势，也可能说明短期过热。

### `vol_20d`

20 日波动率（volatility）。

代码用最近 20 天 `ret_1d` 的标准差：

```text
vol_20d = std(ret_1d over last 20 trading days)
```

它衡量“最近价格有多剧烈波动”。波动高时，预测和交易风险都更高。

### `ma_gap_10d`

价格相对 10 日均线的偏离。

```text
ma_gap_10d = 今天 close / 10 日均线 - 1
```

例：今天 105，10 日均线 100：

```text
ma_gap_10d = 5%
```

它可以表示短期强弱。

### `ma_gap_50d`

价格相对 50 日均线的偏离。

它比 `ma_gap_10d` 更偏中期趋势。

### `range_1d`

当天高低价振幅。

```text
range_1d = (high - low) / close
```

例：high=105，low=99，close=100：

```text
range_1d = 6%
```

它反映日内波动和不确定性。

### `volume_z_20d`

成交量 20 日 z-score。

z-score 的意思是：今天成交量相对过去 20 天平均值，高了多少个标准差。

```text
volume_z_20d = (今天成交量 - 20 日平均成交量) / 20 日成交量标准差
```

例：

```text
今天成交量 = 1500 万
20 日平均 = 1000 万
20 日标准差 = 250 万
volume_z_20d = (1500 - 1000) / 250 = 2
```

这表示今天成交量比平时高 2 个标准差，可能有新闻、资金流入或异常事件。

## warm-up 行是什么

有些特征需要历史窗口才能算出来。

例：`ma_gap_50d` 需要过去 50 天均线。第 1 天到第 49 天没有足够历史，所以这些行是 warm-up rows。

```text
第 1-49 天：无法计算 50 日均线 -> 删除
第 50 天开始：可以计算 50 日均线 -> 保留
```

所以代码会 drop 掉 warm-up 行。

## 样本外测试窗口是什么

样本外（out-of-sample）意思是：模型训练时没见过的数据。

例：

```text
2018-2020：训练窗口 train window
2021-Q1：测试窗口 test window
```

模型只能用 2018-2020 学到的规律去预测 2021-Q1。这样更接近真实交易，因为真实交易时你也看不到未来。

## walk-forward 预测是什么

walk-forward 是量化回测里常用的训练方式。它模拟“时间往前走”的过程。

例：

```text
第 1 次：
2018-2020 训练 -> 预测 2021-Q1

第 2 次：
2018-Q2 到 2021-Q1 训练 -> 预测 2021-Q2

第 3 次：
2018-Q3 到 2021-Q2 训练 -> 预测 2021-Q3
```

每次只用过去数据预测未来。这样可以减少偷看未来。

## 拼接所有样本外预测是什么意思

每个 walk-forward 窗口都会产生一段未来预测。

例：

```text
窗口 1 输出：2021-Q1 的预测
窗口 2 输出：2021-Q2 的预测
窗口 3 输出：2021-Q3 的预测
```

“拼接所有样本外预测”就是把这些预测连起来：

```text
2021-Q1 + 2021-Q2 + 2021-Q3 + ... = 一整条历史预测记录
```

这条记录就像模型在历史上实时运行过一样。后面回测就是基于这条预测记录做的。

### 用一个具体例子彻底讲清楚

假设我们只看一只股票 `AAPL.US`，并且为了方便理解，把每个测试窗口简化成 3 天。

第 1 轮：

```text
训练数据：2021-01-01 到 2023-12-31
预测区间：2024-01-02 到 2024-01-04
```

第 1 轮模型会输出类似这样的结果：

| date | symbol | prob_up | future_ret | 真实结果 |
|---|---|---:|---:|---|
| 2024-01-02 | AAPL.US | 0.60 | 0.010 | 次日上涨 |
| 2024-01-03 | AAPL.US | 0.48 | -0.006 | 次日下跌 |
| 2024-01-04 | AAPL.US | 0.57 | 0.004 | 次日上涨 |

这里的意思是：

```text
2024-01-02 这一天，模型认为 AAPL 下一期上涨概率是 60%。
后来真实发生的收益 future_ret 是 +1.0%。
```

第 2 轮：

```text
训练数据：窗口往前滚动，例如 2021-04-01 到 2024-03-31
预测区间：2024-04-01 到 2024-04-03
```

第 2 轮模型输出：

| date | symbol | prob_up | future_ret | 真实结果 |
|---|---|---:|---:|---|
| 2024-04-01 | AAPL.US | 0.52 | -0.002 | 次日下跌 |
| 2024-04-02 | AAPL.US | 0.61 | 0.008 | 次日上涨 |
| 2024-04-03 | AAPL.US | 0.44 | -0.011 | 次日下跌 |

第 3 轮继续：

| date | symbol | prob_up | future_ret | 真实结果 |
|---|---|---:|---:|---|
| 2024-07-01 | AAPL.US | 0.58 | 0.006 | 次日上涨 |
| 2024-07-02 | AAPL.US | 0.49 | 0.003 | 次日上涨 |
| 2024-07-03 | AAPL.US | 0.62 | -0.004 | 次日下跌 |

“拼接所有样本外预测”就是把这些表按时间接起来：

| 来源轮次 | date | symbol | prob_up | future_ret |
|---|---|---|---:|---:|
| 第 1 轮 | 2024-01-02 | AAPL.US | 0.60 | 0.010 |
| 第 1 轮 | 2024-01-03 | AAPL.US | 0.48 | -0.006 |
| 第 1 轮 | 2024-01-04 | AAPL.US | 0.57 | 0.004 |
| 第 2 轮 | 2024-04-01 | AAPL.US | 0.52 | -0.002 |
| 第 2 轮 | 2024-04-02 | AAPL.US | 0.61 | 0.008 |
| 第 2 轮 | 2024-04-03 | AAPL.US | 0.44 | -0.011 |
| 第 3 轮 | 2024-07-01 | AAPL.US | 0.58 | 0.006 |
| 第 3 轮 | 2024-07-02 | AAPL.US | 0.49 | 0.003 |
| 第 3 轮 | 2024-07-03 | AAPL.US | 0.62 | -0.004 |

这张拼起来的大表，就是：

```text
reports/predictions.parquet
```

它不是训练数据，也不是最终模型。它是一条“历史上每个时间点，当时模型会怎么预测”的记录。

### 这张预测表和回测是什么关系

回测会读取这张拼起来的预测表，然后按交易规则做决策。

当前规则是：

```text
prob_up >= 0.55 -> long，持有股票
prob_up <  0.55 -> flat，空仓
```

继续用上面的例子：

| date | prob_up | 决策 | future_ret | 策略收益 |
|---|---:|---|---:|---:|
| 2024-01-02 | 0.60 | long | 0.010 | 0.010 |
| 2024-01-03 | 0.48 | flat | -0.006 | 0.000 |
| 2024-01-04 | 0.57 | long | 0.004 | 0.004 |
| 2024-04-01 | 0.52 | flat | -0.002 | 0.000 |
| 2024-04-02 | 0.61 | long | 0.008 | 0.008 |
| 2024-04-03 | 0.44 | flat | -0.011 | 0.000 |
| 2024-07-01 | 0.58 | long | 0.006 | 0.006 |
| 2024-07-02 | 0.49 | flat | 0.003 | 0.000 |
| 2024-07-03 | 0.62 | long | -0.004 | -0.004 |

然后把每天的策略收益连乘起来，就得到资金曲线 `equity`。

这就是：

```text
reports/backtest_daily.csv
```

所以三者关系是：

```text
每一轮临时模型 -> 产生一段未来预测
所有轮次预测拼起来 -> reports/predictions.parquet
用 predictions 里的 prob_up 生成 long/flat -> reports/backtest_daily.csv
用 backtest_daily.csv 汇总 total_return / Sharpe / max_drawdown
```

### 为什么不是每一轮单独回测完就结束

如果只看单轮，例如只看 2024-Q1，样本太短，可能只是运气好或运气差。

把所有轮次接起来，相当于问：

```text
如果这个方法从 2024 年开始一直按时间运行到 2026 年，
中间每个季度都重新用过去数据训练一次，
整体资金曲线会是什么样？
```

这比单独看某一轮更接近真实研究。

## look-ahead leakage 是什么

look-ahead leakage 可以理解为“偷看未来”。

错误例子：

```text
用 2025 年的数据训练模型，然后回测 2023 年。
```

这不真实，因为 2023 年交易时不可能知道 2025 年。

另一个错误例子：

```text
用明天的收益生成今天的特征。
```

这会让回测结果虚高，但实盘会失效。

本项目用 walk-forward，是为了尽量避免这类问题。

## long / flat 是什么

`long`：买入或持有多头仓位，股票涨了赚钱，跌了亏钱。

`flat`：空仓，不持有这只股票。

当前 baseline 没做 short（做空），因为做空涉及借券、费用、风险控制，第一版先不加。

## long/flat 决策阈值是什么

配置里的：

```yaml
probability_threshold: 0.55
```

意思是：模型预测上涨概率至少 55% 才买。

例：

| prob_up | 动作 |
|---:|---|
| 0.62 | long |
| 0.56 | long |
| 0.51 | flat |
| 0.40 | flat |

为什么不是 0.50？因为交易有成本，市场有噪声。只比 50% 高一点点可能不够覆盖成本。

## 仓位变化时的交易成本是什么意思

仓位变化就是从不持有变成持有，或从持有变成不持有。

例：

```text
昨天 flat，今天 long -> 买入，产生交易成本
昨天 long，今天 flat -> 卖出，产生交易成本
昨天 long，今天 long -> 没变化，不收成本
```

配置：

```yaml
transaction_cost_bps: 5
```

`bps` 是 basis points，1 bps = 0.01%。5 bps = 0.05%。

交易成本粗略包括佣金、买卖价差、市场冲击等。

## 回测是什么

回测（backtest）就是把一个策略放到历史数据上模拟运行：

```text
如果当时模型给出这个信号，我会不会买？
买了之后收益如何？
考虑交易成本后还赚钱吗？
最大亏损有多大？
```

回测是进入模拟盘和实盘前的最低门槛。

## 回测之后会更新模型吗

当前代码的 walk-forward 已经会在每个窗口重新训练模型。

但完整流程中有两种“更新”：

1. 回测里的重新训练：模拟历史上每个阶段重新训练。
2. 真实运行时的重新训练：比如每天收盘后、每周、每月重新训练。

当前项目先做第 1 种。后续会加定时任务做第 2 种。

## 当前是实时数据还是定时更新

当前不是实时系统。

当前是离线/批处理（batch）：

```text
每天或每隔一段时间拉数据 -> 生成特征 -> 训练/预测 -> 输出信号
```

为什么不一开始做实时在线学习？

1. 实时数据源贵且复杂。
2. 高频实时策略对延迟、撮合、风控要求高。
3. 大多数基本面/新闻/日线策略不需要毫秒级实时。
4. 先把日线/分钟线的稳定流程做好更实际。

后续更合理的演进：

```text
日线批处理 -> 分钟线批处理 -> 准实时信号 -> 实时消费行情
```

当前市场数据接入状态：

```text
代码支持 Tiingo provider
Tiingo 真实历史日线已跑通
baseline 当前使用 tiingo，不再使用 synthetic_fallback
```

所以现在可以说“历史日线市场数据已经接入成功”。但这仍然不是实时行情，也不是券商交易接口。

## 为什么说股票池和回测框架还要做扎实

当前工程已经跑通了真实 Tiingo 行情和 baseline 回测，但这不等于可以实盘。

### 股票池问题

当前股票池只有：

```text
AAPL.US, MSFT.US, NVDA.US, SPY.US
```

这只是工程测试，不是严谨研究。正式策略需要更大的股票池，并处理行业集中、流动性、幸存者偏差、指数成分历史变化等问题。

### 回测问题

当前回测只验证最简单规则：

```text
prob_up >= 0.55 -> long
prob_up < 0.55 -> flat
```

还没有完整处理：

```text
下单时间
滑点
仓位大小
组合约束
风控
基准对比
参数过拟合
交易日志
```

所以现在的正确定位是：

```text
工程链路已跑通
策略还不能实盘
后续逐步把研究和风控做扎实
```

## Parquet 是什么

Parquet 是一种列式数据文件格式（columnar file format）。

你可以把它理解成“适合大数据分析的 CSV/Excel 替代品”。

优点：

1. 读取快。
2. 压缩好。
3. 保存字段类型。
4. 很适合 pandas、polars、DuckDB、Spark 等工具。

本项目用 Parquet 保存：

```text
prices.parquet          原始/清洗后行情
price_features.parquet  特征表
predictions.parquet     模型预测
```

## DuckDB 是什么

DuckDB 是一个嵌入式分析型数据库（embedded analytical database）。

你可以把它理解成：

```text
SQLite 更适合小型事务数据库
DuckDB 更适合本地数据分析和 SQL 查询
```

它不需要启动数据库服务，直接一个 `.duckdb` 文件就能用。

本项目里：

```text
data/quant.duckdb
```

里面创建了几个视图：

```sql
prices
price_features
predictions
```

你以后可以用 SQL 查：

```sql
select symbol, avg(prob_up)
from predictions
group by symbol;
```

## 回测指标解释

### total return

总收益。

例：初始 100 万，最后 120 万：

```text
total return = 20%
```

### annual return

年化收益。把总收益换算成平均每年收益。

### annual volatility

年化波动率。衡量收益曲线波动有多大。

波动越高，持有体验越不稳定。

### Sharpe

Sharpe ratio，夏普比率。粗略理解：

```text
每承担一单位波动，换来多少收益
```

越高越好，但不能只看 Sharpe。

### max drawdown

最大回撤。表示从历史高点到低点最大亏损幅度。

例：账户从 100 万涨到 150 万，再跌到 105 万：

```text
max drawdown = (105 - 150) / 150 = -30%
```

这是非常重要的风控指标。

### turnover

换手率。表示仓位变化频率。

换手率高，交易成本更高，也更容易被滑点影响。

### hit rate

胜率。这里是“持仓时，下一期真的上涨的比例”。

胜率高不一定赚钱，因为亏损可能比盈利大。

### exposure

暴露度。表示平均有多少时间/标的处于持仓状态。

例：`exposure = 0.24` 表示大约 24% 的股票-日期组合处于 long 状态。

## AUC 和 log_loss 是什么

### AUC

AUC 用来衡量模型排序能力。

简单理解：模型能不能把更可能上涨的样本排在更前面。

```text
AUC = 0.5 约等于随机猜
AUC > 0.5 有一点排序能力
AUC 越高越好
```

金融里 AUC 很难高，轻微高于 0.5 也可能有研究价值，但必须经过交易成本和回测验证。

### log_loss

log_loss 衡量概率预测有多准。

如果模型非常自信但猜错，会被重罚。

例：

```text
真实上涨，但模型只给 0.05 概率 -> 惩罚很大
真实上涨，模型给 0.55 概率 -> 惩罚较小
```

log_loss 越低越好。

## 为什么优先 XGBoost，fallback 到 RandomForest

XGBoost 是表格数据（tabular data）上非常强的 baseline，量化特征通常也是表格数据。

优点：

1. 对非线性关系处理好。
2. 不需要像神经网络那样大量调参。
3. 在中小数据上通常很稳。
4. 训练速度快。

Fallback 到 RandomForest 是为了工程鲁棒性：

```text
如果 xgboost 安装失败或环境不支持，baseline 仍然能跑通。
```

RandomForest 不是当前首选，只是备用模型。

## XGBoost 参数为什么这么设

当前参数是保守 baseline，不是最终最优参数：

| 参数 | 当前值 | 含义 | 为什么先这样设 |
|---|---:|---|---|
| `n_estimators` | 200 | 树的数量 | 不太少，也不会太慢 |
| `max_depth` | 3 | 每棵树最大深度 | 浅树，降低过拟合 |
| `learning_rate` | 0.05 | 学习率 | 保守，每棵树只做小修正 |
| `subsample` | 0.8 | 每棵树用 80% 样本 | 增加随机性，降低过拟合 |
| `colsample_bytree` | 0.8 | 每棵树用 80% 特征 | 降低对单一特征依赖 |
| `eval_metric` | logloss | 概率损失 | 适合二分类概率预测 |
| `tree_method` | hist | 直方图算法 | 训练快，适合 baseline |
| `random_state` | 42 | 固定随机种子 | 结果可复现 |

后续需要用 walk-forward 调参，而不是看一次结果手动调。

## 滑点是什么

滑点（slippage）是“你以为能成交的价格”和“实际成交价格”之间的差。

例：

```text
模型信号出现时价格 100
实际买入成交价 100.10
滑点 = 0.10%
```

滑点来源：

1. 市场价格变化。
2. 买卖盘不够厚。
3. 下单延迟。
4. 大单冲击市场。

## 滑点模型是什么

滑点模型就是在回测里模拟真实成交不可能总在理想价格。

简单模型：

```text
每次交易额外扣 5 bps
```

复杂模型：

```text
滑点 = 基础滑点 + 成交量占比 * 冲击系数 + 波动率调整
```

没有滑点模型的回测通常会过于乐观。

## 对账是什么

对账（reconciliation）是实盘或模拟盘里必须做的检查：

```text
系统认为的持仓
vs
券商账户真实持仓
```

例：

```text
系统以为持有 AAPL 100 股
券商实际显示 AAPL 0 股
```

这说明订单失败、接口异常、状态同步错误，必须停止自动交易并报警。

## 为什么需要环境启动脚本

换机器或重装环境时，需要一键把 `.venv` 和目录准备好。

所以仓库里提供：

```bash
scripts/env/bootstrap_server.sh
```

在项目目录运行：

```bash
cd /root/sanmao-ai/sanmao-llm
bash scripts/env/bootstrap_server.sh
```

它会检查/创建 `.venv`，安装依赖，并提示测试和 baseline 命令。
