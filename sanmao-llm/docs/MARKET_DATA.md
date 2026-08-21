# 市场数据源选型（Market Data）

稳定市场数据源是必须项。没有可靠的真实行情，模型和回测都只能停留在工程 smoke test。

## 当前结论

免费公共源不适合作为长期稳定依赖：

| 数据源 | 当前判断 |
|---|---|
| Yahoo / yfinance | 方便，但服务器实测被限流，不稳定 |
| Stooq | 服务器实测返回 API key/captcha 提示 |
| Alpha Vantage | 可接入，需要 API key，免费额度有限 |
| Tiingo | 可接入，需要 API key，质量较好，适合历史日线 |
| Finnhub | 可接入，需要 API key，更偏综合金融 API |
| Nasdaq Data Link / Quandl | 适合部分宏观、替代数据和商业数据集 |
| SEC EDGAR | 免费、官方、稳定，适合公告/财报事件 |

当前代码已实现：

```text
yfinance
yahoo_chart
alpha_vantage
tiingo
synthetic
```

当前项目已接入并验证：

```text
provider: tiingo
status: 真实历史日线已跑通
synthetic fallback: 已关闭
```

## 推荐优先级

### 第一选择：Tiingo

适合目标：

```text
美股历史日线
ETF
较稳定的数据质量
研究和回测
```

需要：

```bash
export TIINGO_API_KEY="你的 key"
```

测试：

```bash
.venv/bin/python scripts/verify/check_market_data.py --provider tiingo
```

配置：

```yaml
market_data_provider: "tiingo"
allow_synthetic_fallback: false
```

当前 baseline 已采用这个配置。

### 第二选择：Alpha Vantage

适合目标：

```text
快速拿到股票、外汇、加密货币、技术指标等数据
```

需要：

```bash
export ALPHA_VANTAGE_API_KEY="你的 key"
```

测试：

```bash
.venv/bin/python scripts/verify/check_market_data.py --provider alpha_vantage
```

配置：

```yaml
market_data_provider: "alpha_vantage"
allow_synthetic_fallback: false
```

注意：Alpha Vantage 免费额度通常较紧，批量股票回测可能很快触发限制。

### 第三选择：本地 CSV/Parquet 导入

如果你能从其他渠道下载历史行情，最稳的方式是导入本地文件：

```text
date, open, high, low, close, volume, symbol
```

后续可以新增 `local_csv` / `local_parquet` provider。这个方向适合大规模回测，因为数据不会受 API 限流影响。

## 为什么不继续依赖 yfinance

`yfinance` 很适合本地研究，但不是正式数据源。

部分服务器环境实测：

```text
YFRateLimitError('Too Many Requests. Rate limited. Try after a while.')
```

这说明它在机房出口环境下不稳定。可以保留为备用，但不能作为主 provider。

## synthetic fallback 的定位

`synthetic_fallback` 是合成行情，只用于验证代码链路。

它能证明：

```text
数据 -> 特征 -> 模型 -> 回测 -> 报告
```

能跑通。

它不能证明：

```text
策略有效
模型有预测力
可以实盘交易
```

只要进入真实研究阶段，应设置：

```yaml
allow_synthetic_fallback: false
```

这样真实数据源失败时会直接报错，而不是悄悄使用合成数据。

## 下一步

1. 申请 Tiingo 或 Alpha Vantage API key。
2. 在服务器环境变量中配置 key。
3. 用 `scripts/verify/check_market_data.py` 验证真实数据。
4. 把 `allow_synthetic_fallback` 改成 `false`。
5. 重新跑 baseline，确认 `data_provider_used` 不是 `synthetic_fallback`。

## Tiingo News 状态

Tiingo News 使用同一个 `TIINGO_API_KEY`，但是否能访问取决于账户套餐权限。

服务器实测当前 token：

```text
GET https://api.tiingo.com/tiingo/news
status: 403
{"detail":"You do not have permission to access the News API"}
```

结论：

```text
Tiingo 日线价格已可用
Tiingo News 当前无权限
```

代码已新增：

```text
src/quant_llm/news.py
scripts/run/fetch_tiingo_news.py
```

如果后续开通 News 权限，可以运行：

```bash
.venv/bin/python scripts/run/fetch_tiingo_news.py \
  --symbols AAPL.US MSFT.US NVDA.US SPY.US \
  --start-date 2024-01-01 \
  --end-date 2024-12-31 \
  --output data/news/tiingo_news.csv
```

然后在 `config/baseline.yaml` 中把 `text_features.news_csv` 指向这个文件。

## SEC EDGAR 免费公告源

SEC EDGAR 是免费官方数据源，适合获取：

```text
8-K
10-Q
10-K
```

它不是新闻媒体，但对量化很有价值，因为它覆盖公司正式公告、季度报告、年度报告和重大事项。

当前已实现：

```text
src/quant_llm/news.py
scripts/run/fetch_sec_filings.py
config/sec_filings_baseline.yaml
```

拉取 SEC filings：

```bash
.venv/bin/python scripts/run/fetch_sec_filings.py \
  --symbols AAPL.US MSFT.US NVDA.US \
  --start-date 2021-01-01 \
  --end-date 2026-05-31 \
  --output data/news/sec_filings.csv
```

运行 SEC filings baseline：

```bash
.venv/bin/python scripts/run/run_baseline.py --config config/sec_filings_baseline.yaml
```

当前服务器验证：

```text
SEC filings rows: 150
text_events: 150
daily_text_features: 125
training_features: 5228
providers: ['tiingo']
```

## GDELT 免费新闻源

GDELT 是免费全球新闻源，不需要 API key。当前已实现：

```text
fetch_gdelt_news
scripts/run/fetch_gdelt_news.py
config/gdelt_news_baseline.yaml
```

小规模 smoke test 已跑通：

```bash
.venv/bin/python scripts/run/fetch_gdelt_news.py \
  --symbols AAPL.US MSFT.US \
  --start-date 2024-05-01 \
  --end-date 2024-05-31 \
  --maxrecords-per-symbol 3 \
  --output data/news/gdelt_news_smoke.csv
```

验证结果：

```text
saved 6 GDELT news rows
symbols: ['AAPL.US', 'MSFT.US']
```

注意：

1. GDELT 免费，但有请求限流，适合分批慢抓。
2. GDELT 的 ticker 关联不如 Tiingo News/Finnhub company-news 精确。
3. 简单关键词如 `Apple` 会抓到噪音，例如音乐、普通苹果、非股票语境。
4. 后续必须做来源过滤、语言过滤、ticker linking 和去重。

当前定位：

```text
GDELT = 免费补充新闻源
SEC EDGAR = 免费官方公告源
Tiingo daily = 真实价格源
```
# BaoStock A 股数据源

BaoStock 可以作为第一版 A 股历史日线数据源。

定位：

```text
适合：A 股历史行情研究、离线回测、基础财务数据
不适合：实时交易、券商下单、账户持仓查询
```

当前项目已支持：

```text
market_data_provider: baostock
```

项目内部 symbol：

```text
600000.SH
000001.SZ
```

会自动转换成 BaoStock 格式：

```text
sh.600000
sz.000001
```

示例：

```bash
.venv/bin/python scripts/run/run_a_share_baostock.py
.venv/bin/python scripts/run/run_baseline.py --config config/a_share_baostock.yaml
```

如果要扩大 A 股样本，不要继续只跑两三只股票。先生成股票池文件：

```bash
.venv/bin/python scripts/run/build_a_share_universe.py \
  --trade-date 2026-05-29 \
  --universe hs300 \
  --output config/cn_a_hs300_symbols.txt
```

然后用专门配置跑：

```bash
.venv/bin/python scripts/run/run_baseline.py --config config/a_share_baostock_hs300.yaml
```

风险：

```text
1. BaoStock 不是券商接口，不能下单。
2. 数据质量、复权规则、停牌、涨跌停仍需要做校验。
3. 实盘前必须用券商数据或其他可靠数据源交叉验证。
```
