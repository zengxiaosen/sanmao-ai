# A 股适配计划

这份文档说明为什么要把 A 股、美股、港股分层适配，以及后续接 A 股券商时应该怎么做。

## 结论

项目不能把所有市场写成一套死逻辑。

合理分层是：

```text
模型层：
  只输出 prob_up、预期收益、风险概率。

策略层：
  把模型输出变成目标仓位，例如 long/flat、等权、最大仓位。

市场规则层：
  处理 T+1、100 股一手、涨跌停、停牌、是否允许小数股。

券商适配层：
  处理 Alpaca、QMT、PTrade、IBKR 等不同下单 API。
```

当前代码已经新增：

```text
src/quant_llm/market_rules.py
```

里面有：

```text
US_EQUITY_RULES       美股：允许小数股，当前用于 Alpaca paper
CHINA_A_RULES         A 股：100 股一手，T+1，不允许小数股
HK_EQUITY_RULES       港股：预留，后续要按具体股票 lot size 细化
```

## A 股和美股的核心差异

| 项目 | 美股 / Alpaca paper | A 股 |
|---|---|---|
| 交易单位 | 可小数股 | 普通买入 100 股一手 |
| 交易制度 | 通常 T+0 | 股票 T+1 |
| 涨跌停 | 通常无固定 10% 涨跌停 | 主板/创业板/科创板规则不同 |
| 做空 | 美股更容易 | 普通个人很难做空 |
| 券商 API | Alpaca REST 简单 | QMT / PTrade 通常依赖券商客户端 |
| 数据 | Tiingo/Yahoo/Alpaca | Tushare/AkShare/BaoStock/券商数据 |

所以同一个策略信号：

```text
prob_up >= 0.55 -> 想要 long
```

在美股可以变成：

```text
买入 58.549381 股 MSFT
```

但在 A 股必须变成：

```text
买入 200 股或 300 股，不能买 258.3 股
```

这就是市场规则层存在的原因。

## A 股数据源路线

第一阶段建议先做日线，不急着做 tick 或分钟线。

候选：

```text
Tushare Pro:
  数据较全，常用，需要 token。

AkShare:
  免费，覆盖广，但稳定性和字段一致性要验证。

BaoStock:
  免费，适合基础日线和财务数据。

券商 QMT 数据:
  如果你开通 QMT，后续可以直接用券商本地行情。
```

建议顺序：

```text
1. 先接 Tushare / AkShare / BaoStock 中一个，跑通 A 股日线研究。
2. 再接 QMT / PTrade 的券商数据和模拟交易。
3. 最后才考虑真实账户小权限实盘。
```

当前已接入 BaoStock 日线数据源：

```text
market_data_provider: baostock
config/a_share_baostock.yaml
scripts/run/run_a_share_baostock.py
```

运行数据源验证：

```bash
.venv/bin/python scripts/run/run_a_share_baostock.py
```

运行 A 股 BaoStock baseline 回测：

```bash
.venv/bin/python scripts/run/run_baseline.py --config config/a_share_baostock.yaml
```

如果要把样本从“两只股票”提升到“几百只股票”，先生成股票池：

```bash
.venv/bin/python scripts/run/build_a_share_universe.py \
  --trade-date 2026-05-29 \
  --universe hs300 \
  --output config/cn_a_hs300_symbols.txt
```

然后运行：

```bash
.venv/bin/python scripts/run/run_baseline.py --config config/a_share_baostock_hs300.yaml
```

注意：

```text
BaoStock 不是券商交易接口，不能下单。
它只解决 A 股历史行情/研究数据问题。
```

当前服务器验证结果：

```text
数据源：BaoStock
股票池：600000.SH, 000001.SZ
数据行数：2614
训练特征行数：2514
样本外预测行数：1002
```

第一版价格特征 baseline 回测：

```text
total_return: -3.69%
annual_return: -1.87%
sharpe: -0.236
max_drawdown: -16.10%
```

模型晋级结果：

```text
promoted_to_latest: false
```

原因：

```text
annual_return < 0
sharpe < 0
```

这说明 BaoStock 数据源已经打通，但当前 A 股策略质量不达标，不能用于模拟盘或实盘。

## A 股券商路线

常见个人量化接入：

```text
QMT:
  国内券商较常见，通常需要安装客户端/miniQMT。
  Python 接口围绕本地客户端运行。

PTrade:
  一些券商支持，通常也要券商开通。

IBKR:
  可交易部分中国相关产品，但对 A 股个人直连不一定是最合适路径。
```

后续需要你确认：

```text
1. 你使用哪家券商。当前计划：国金证券。
2. 是否能开通 QMT 或 PTrade。当前计划：国金 QMT / 智能策略交易终端。
3. 是 Windows 本地客户端，还是服务器可访问的网关。QMT 通常需要本地客户端。
4. 是否有模拟盘/sandbox。优先使用模拟盘。
```

## 国金 QMT 你现在需要做什么

你现在最重要的不是直接实盘，而是把 QMT 模拟环境准备好。

请按顺序做：

```text
1. 联系国金客户经理或交易软件入口，确认已开通 QMT/miniQMT/智能策略交易终端权限。
2. 确认是否有模拟交易/仿真交易环境。
3. 安装国金 QMT 或 miniQMT。大概率需要 Windows 本地机器。
4. 确认 Python 示例能 import xtquant。
5. 找到 QMT 客户端安装路径。
6. 确认 account_id、account_type、session_id 的写法。
7. 不要先给真实资金账户自动下单权限。
```

本项目已新增环境检测脚本：

```bash
python scripts/verify/check_qmt_env.py
```

它只检查：

```text
xtquant 是否可 import
QMT_ACCOUNT_ID 是否配置
QMT_CLIENT_PATH 是否存在
trading_mode 是否是 paper/simulation
```

它不会连接账户，也不会下单。

QMT 真实配置不要写进 Git，写到运行机器 `.env`：

```text
QMT_ACCOUNT_ID=
QMT_ACCOUNT_TYPE=STOCK
QMT_CLIENT_PATH=
QMT_SESSION_ID=1001
QMT_TRADING_MODE=paper
```

## A 股适配必须补的规则

当前 `CHINA_A_RULES` 只做了最基础的：

```text
100 股一手
T+1 标记
不允许小数股
不允许做空
```

后续要补：

```text
1. 交易日历：节假日、调休、半日市。
2. 涨跌停：普通股票、ST、科创板、创业板规则不同。
3. 停牌：停牌当天不能买卖。
4. 一字涨停/跌停：有信号也可能成交不了。
5. T+1 可卖数量：今天买入的股票今天不能卖。
6. 100 股一手：买入按 100 股，卖出可处理零股规则。
7. 费用：佣金、印花税、过户费。
8. 最小价格变动单位：通常 0.01 元。
9. ST/退市风险过滤。
```

## 后续代码规划

建议新增：

```text
src/quant_llm/market_rules.py        已新增
src/quant_llm/brokers/alpaca.py      后续可从 broker.py 拆出
src/quant_llm/brokers/qmt.py         待接 QMT
src/quant_llm/brokers/ptrade.py      待接 PTrade
src/quant_llm/data_a_share.py        A 股行情数据源
config/a_share_baseline.yaml         A 股研究配置
scripts/run/run_a_share_all.sh       A 股研究总入口
```

## 实盘前判断

A 股更适合个人研究，不等于更容易赚钱。

真正进入 A 股实盘前，需要至少满足：

```text
1. A 股日线数据稳定。
2. 回测已处理 T+1、涨跌停、停牌、费用。
3. 模拟盘连续运行并对账。
4. broker adapter 有重复提交保护。
5. 有 kill switch。
6. 单笔/单日/单票风险限制明确。
7. 真实账户只给小资金、小权限。
```

当前阶段：先把美股 Alpaca paper 作为工程闭环样板，同时设计 A 股适配层。
