// factor-dict.ts —— 因子字典：每个因子的人话解释。
// 看板到处要解释「这个因子是什么」，集中放这里，页面统一查询。
// 目标读者是完全没接触过量化的人，解释里不出现新的术语。

export interface FactorInfo {
  name: string;        // 中文短名（图表里显示）
  meaning: string;     // 一句人话：它衡量什么
  calc: string;        // 怎么算出来的（小白能看懂）
  group: string;       // 大类
}

export const FACTOR_DICT: Record<string, FactorInfo> = {
  // ===== 量价（看股票自己的价格和成交量）=====
  ret_1d:      { group: '量价', name: '1日涨幅',   meaning: '昨天涨了多少', calc: '今收 ÷ 昨收 − 1' },
  ret_5d:      { group: '量价', name: '5日涨幅',   meaning: '最近一周涨了多少（短期动量）', calc: '今收 ÷ 5天前收盘 − 1' },
  ret_20d:     { group: '量价', name: '20日涨幅',  meaning: '最近一个月涨了多少（中期动量）', calc: '今收 ÷ 20天前收盘 − 1' },
  vol_20d:     { group: '量价', name: '20日波动率', meaning: '最近一个月每天上蹿下跳的剧烈程度', calc: '近20天日涨跌幅的标准差' },
  ma_gap_10d:  { group: '量价', name: '偏离10日均线', meaning: '现价比近两周平均价高/低多少（短期超买超卖）', calc: '今收 ÷ 10日均价 − 1' },
  ma_gap_50d:  { group: '量价', name: '偏离50日均线', meaning: '现价比近两个半月平均价高/低多少（中期趋势位置）', calc: '今收 ÷ 50日均价 − 1' },
  range_1d:    { group: '量价', name: '日内振幅',  meaning: '当天最高最低价差距多大（当日多空拉锯强度）', calc: '(最高 − 最低) ÷ 收盘' },
  volume_z_20d:{ group: '量价', name: '异常成交量', meaning: '今天的成交量比平时反常多少（放量=有事发生）', calc: '(今量 − 20日均量) ÷ 20日量标准差' },

  // ===== 舆情（看这家公司的公告/新闻，来源：SEC 官方公告）=====
  llm_news_count:         { group: '舆情', name: '当日公告数',   meaning: '公司当天发布了几条官方公告', calc: '统计当日 SEC EDGAR（美国证监会官方信息披露库）里该公司的公告条数：8-K 重大事件 / 10-Q 季报 / 10-K 年报' },
  llm_mean_sentiment:     { group: '舆情', name: '平均情绪',     meaning: '今天的公告整体偏利好还是利空（−1 最空，+1 最多）', calc: '每条公告文本打情绪分后取平均' },
  llm_weighted_sentiment: { group: '舆情', name: '加权情绪',     meaning: '同上，但「越有把握的判断权重越大」', calc: '情绪分 × 置信度 后取平均' },
  llm_max_confidence:     { group: '舆情', name: '最高置信度',   meaning: '今天最有把握的一条判断有多确定', calc: '当日各条置信度的最大值' },
  event_earnings_count:   { group: '舆情', name: '财报事件数',   meaning: '今天有没有财报类公告（季报/年报）', calc: '当日事件类型=财报 的条数' },
  event_macro_count:      { group: '舆情', name: '宏观事件数',   meaning: '今天有没有涉及利率/通胀等宏观话题的公告', calc: '当日事件类型=宏观 的条数' },
  risk_margin_pressure_count: { group: '舆情', name: '利润承压信号', meaning: '公告里提到利润率压力的次数', calc: '当日风险标签=margin_pressure 的条数' },
  risk_guidance_weak_count:   { group: '舆情', name: '指引疲软信号', meaning: '公告里业绩指引不及预期的次数', calc: '当日风险标签=guidance_weak 的条数' },
  risk_supply_chain_count:    { group: '舆情', name: '供应链风险信号', meaning: '公告里提到供应链问题的次数', calc: '当日风险标签=supply_chain 的条数' },

  // ===== 宏观（看整个市场的大环境，来源：美联储官方数据库 FRED）=====
  vix_level:      { group: '宏观', name: 'VIX恐慌指数', meaning: '整个市场现在多害怕（>25 算恐慌）', calc: 'CBOE VIX 指数当日收盘值' },
  vix_change_5d:  { group: '宏观', name: 'VIX 5日变化', meaning: '恐慌情绪最近一周是在升温还是降温', calc: '今日 VIX − 5天前 VIX' },
  ust10y_level:   { group: '宏观', name: '10年美债利率', meaning: '市场基准利率水平（利率高→科技股估值承压）', calc: '10年期美债收益率（%）' },
  ust10y_change_5d:{ group: '宏观', name: '利率5日变化', meaning: '利率最近一周升得快不快（快速上行是科技股大敌）', calc: '今日利率 − 5天前利率' },
  dxy_change_5d:  { group: '宏观', name: '美元5日变化', meaning: '美元最近一周走强还是走弱（美元强→资金回流美国）', calc: '美元指数 5 日涨跌幅' },
};

/** 查因子信息；查不到给一个不撒谎的兜底。 */
export function factorInfo(key: string): FactorInfo {
  return FACTOR_DICT[key] ?? { group: '其他', name: key, meaning: '（暂无说明）', calc: '' };
}

/** 图表里显示「中文名 key」双行标签用。 */
export function factorLabel(key: string): string {
  const info = FACTOR_DICT[key];
  return info ? `${info.name}` : key;
}
