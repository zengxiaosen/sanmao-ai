from __future__ import annotations


# factor_names.py —— 因子中文名与分组（后端版）。
# review.py 生成的复盘报告直接面向最终用户，不能出现 ret_1d 这类代码名。
# 前端有一份对应的 factor-dict.ts，两边改名要同步。


FACTOR_NAMES = {
    # 量价
    "ret_1d": "1日涨幅",
    "ret_5d": "5日涨幅",
    "ret_20d": "20日涨幅",
    "vol_20d": "20日波动率",
    "ma_gap_10d": "偏离10日均线",
    "ma_gap_50d": "偏离50日均线",
    "range_1d": "日内振幅",
    "volume_z_20d": "异常成交量",
    # 舆情（SEC 公告）
    "llm_news_count": "当日公告数",
    "llm_mean_sentiment": "公告平均情绪",
    "llm_weighted_sentiment": "公告加权情绪",
    "llm_max_confidence": "公告最高置信度",
    "event_earnings_count": "财报事件数",
    "event_macro_count": "宏观事件数",
    "risk_margin_pressure_count": "利润承压信号",
    "risk_guidance_weak_count": "指引疲软信号",
    "risk_supply_chain_count": "供应链风险信号",
    # 宏观（FRED）
    "vix_level": "VIX恐慌指数",
    "vix_change_5d": "VIX 5日变化",
    "ust10y_level": "10年美债利率",
    "ust10y_change_5d": "利率5日变化",
    "dxy_change_5d": "美元5日变化",
}

GROUP_NAMES = {
    "price_volume": "量价类",
    "sentiment": "舆情类",
    "macro": "宏观类",
}


def cn(factor: str) -> str:
    """因子代码 -> 中文名；没收录的原样返回。"""
    return FACTOR_NAMES.get(factor, factor)


def group_cn(group: str) -> str:
    return GROUP_NAMES.get(group, group)
