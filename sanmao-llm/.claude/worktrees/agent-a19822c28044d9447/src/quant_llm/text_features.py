from __future__ import annotations

from dataclasses import dataclass
import ast
from pathlib import Path

import pandas as pd


TEXT_FEATURE_COLUMNS = [
    # 当天该股票相关文本数量。新闻越多，说明信息密度越高。
    "llm_news_count",
    # 当天 sentiment 的简单平均值。正数偏利好，负数偏利空。
    "llm_mean_sentiment",
    # sentiment * confidence 后的平均值。高置信度文本权重更大。
    "llm_weighted_sentiment",
    # 当天最高 confidence。表示当天是否至少有一条“抽取很确定”的文本。
    "llm_max_confidence",
    # 当天 earnings 类型事件数量。
    "event_earnings_count",
    # 当天 macro 类型事件数量。
    "event_macro_count",
    # 当天毛利率/利润率压力风险出现次数。
    "risk_margin_pressure_count",
    # 当天业绩指引偏弱风险出现次数。
    "risk_guidance_weak_count",
    # 当天供应链风险出现次数。
    "risk_supply_chain_count",
]


@dataclass(frozen=True)
class TextEvent:
    """一条文本被抽取后的结构化事件。

    可以把它理解成“LLM/规则抽取器给一条新闻贴的标签”。

    字段解释：
        date: 事件日期，按天对齐到行情数据。
        symbol: 股票代码，例如 AAPL.US。
        event_type: 事件类型，例如 earnings/macro/supply_chain。
        sentiment: 文本方向，-1 到 1；负数利空，正数利好。
        confidence: 抽取置信度，0 到 1；不是上涨概率。
        impact_horizon: 预计影响期限，例如 1-5d。
        risk_tags: 风险标签列表；空 tuple 表示没有明确风险标签。
    """

    date: pd.Timestamp
    symbol: str
    event_type: str
    sentiment: float
    confidence: float
    impact_horizon: str
    risk_tags: tuple[str, ...]


class RuleBasedTextExtractor:
    """规则版文本抽取器，用关键词模拟 LLM 输出。

    它不是智能模型，只是为了：
        1. 没有 GPU/模型时也能跑完整 pipeline。
        2. 让下游代码先固定输入输出格式。
        3. 作为 LLM 失败时的 fallback。

    真正的本地 Qwen 抽取器在 llm_extractor.py。
    """

    positive_words = {
        "beat",
        "beats",
        "above expectations",
        "record",
        "strong",
        "growth",
        "optimism",
        "surges",
        "buyback",
        "raises",
        "cut rates",
        "supporting",
    }
    negative_words = {
        "misses",
        "below expectations",
        "weak",
        "weakens",
        "disappoints",
        "slowdown",
        "constraints",
        "risk",
        "risks",
        "inflation",
        "recession",
        "pressure",
        "headwinds",
    }

    def extract(self, row: pd.Series) -> TextEvent:
        # 把标题和正文拼在一起做关键词匹配。
        # lower() 是为了大小写不敏感，例如 Beat/beat 都能匹配。
        text = f"{row.get('title', '')} {row.get('body', '')}".lower()

        # 统计正面/负面关键词命中数。
        # 这只是一个很粗糙的模拟，不能当成真实情绪模型。
        positive_hits = sum(1 for word in self.positive_words if word in text)
        negative_hits = sum(1 for word in self.negative_words if word in text)

        # raw_score > 0 偏利好，< 0 偏利空。
        raw_score = positive_hits - negative_hits

        # 除以 5 是为了把分数压到 -1 到 1 附近。
        # max/min 是边界保护，避免超过合法 sentiment 范围。
        sentiment = max(-1.0, min(1.0, raw_score / 5.0))

        # 命中关键词越多，说明文本里可判断的信息越多，confidence 稍高。
        # 最高限制到 0.95，避免规则抽取器假装“百分百确定”。
        confidence = min(0.95, 0.55 + 0.08 * (positive_hits + negative_hits))

        # 事件类型是后续模型特征。这里用关键词粗分：
        #   fed/rate/inflation -> macro
        #   earnings/revenue/guidance -> earnings
        #   其他 -> other
        if "fed" in text or "rate" in text or "inflation" in text:
            event_type = "macro"
            impact_horizon = "1-20d"
        elif "earnings" in text or "revenue" in text or "guidance" in text:
            event_type = "earnings"
            impact_horizon = "1-5d"
        else:
            event_type = "other"
            impact_horizon = "1-5d"

        # risk_tags 是风险标签数组。
        # 空数组/空 tuple 表示没有抽取到明确风险，不是错误。
        risk_tags: list[str] = []
        if "margin" in text or "pressure" in text:
            risk_tags.append("margin_pressure")
        if "guidance" in text and ("weak" in text or "soft" in text or "disappoint" in text):
            risk_tags.append("guidance_weak")
        if "supply" in text or "constraints" in text:
            risk_tags.append("supply_chain")

        return TextEvent(
            date=pd.Timestamp(row["date"]).normalize(),
            symbol=str(row["symbol"]),
            event_type=event_type,
            sentiment=sentiment,
            confidence=confidence,
            impact_horizon=impact_horizon,
            risk_tags=tuple(risk_tags),
        )


def load_news_csv(path: str | Path) -> pd.DataFrame:
    """读取新闻 CSV，并做最基本的字段校验。

    必须有四列：
        date: 新闻日期。
        symbol: 股票代码。
        title: 标题。
        body: 正文或摘要。

    返回结果会按 symbol/date 排序，方便后续和行情按日期拼接。
    """
    frame = pd.read_csv(path, parse_dates=["date"])
    required = {"date", "symbol", "title", "body"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing news columns: {sorted(missing)}")
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    return frame.sort_values(["symbol", "date"]).reset_index(drop=True)


def parse_risk_tags(value) -> list[str]:
    """把 CSV/Parquet 里读出来的 risk_tags 统一转成 list[str]。

    为什么需要这个函数：
        LLM extractor 写 CSV 时，risk_tags 可能被保存成字符串：
            "['margin_pressure']"
        也可能是空数组字符串：
            "[]"
        如果从 Parquet 读，可能已经是 list/tuple。

    这里统一成 Python list，后续判断：
        "margin_pressure" in tags
    才可靠。
    """
    if value is None:
        return []
    if isinstance(value, float) and pd.isna(value):
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(tag) for tag in value]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped or stripped == "[]":
            return []
        try:
            parsed = ast.literal_eval(stripped)
        except (SyntaxError, ValueError):
            return [stripped]
        if isinstance(parsed, (list, tuple, set)):
            return [str(tag) for tag in parsed]
        return [str(parsed)]
    return [str(value)]


def load_text_events_csv(path: str | Path) -> pd.DataFrame:
    """读取已经由 LLM/规则抽取器生成好的结构化事件 CSV。

    和 load_news_csv 的区别：
        load_news_csv 读取原始文本：date/symbol/title/body。
        load_text_events_csv 读取已抽取事件：date/symbol/event_type/sentiment/confidence/impact_horizon/risk_tags。

    用途：
        run_all.sh 会先调用 Qwen 生成 events_csv，然后 run_baseline.py 直接读取它。
        这样训练链路不需要每次临时调用 LLM，也不会依赖用户手工分两步运行。
    """
    frame = pd.read_csv(path, parse_dates=["date"])
    required = {"date", "symbol", "event_type", "sentiment", "confidence", "impact_horizon", "risk_tags"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing text event columns: {sorted(missing)}")
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame["symbol"] = frame["symbol"].astype(str)
    frame["event_type"] = frame["event_type"].astype(str)
    frame["sentiment"] = pd.to_numeric(frame["sentiment"], errors="coerce").fillna(0.0).clip(-1.0, 1.0)
    frame["confidence"] = pd.to_numeric(frame["confidence"], errors="coerce").fillna(0.5).clip(0.0, 1.0)
    frame["impact_horizon"] = frame["impact_horizon"].astype(str)
    frame["risk_tags"] = frame["risk_tags"].apply(parse_risk_tags)
    return frame.sort_values(["symbol", "date"]).reset_index(drop=True)


def extract_text_events(news: pd.DataFrame, extractor: RuleBasedTextExtractor | None = None) -> pd.DataFrame:
    """把新闻表逐条转成结构化事件表。

    输入 news：
        一行一条新闻。

    输出 events：
        一行一个 TextEvent，包含 event_type/sentiment/confidence/risk_tags。

    extractor:
        默认用规则抽取器。也可以传入有 extract(row) 方法的 LLM 抽取器。
    """
    extractor = extractor or RuleBasedTextExtractor()

    # 逐行抽取。第一版为了可读性先用 iterrows。
    # 后续如果文本量很大，可以改成批量推理或服务化推理。
    events = [extractor.extract(row) for _, row in news.iterrows()]
    rows = [
        {
            "date": event.date,
            "symbol": event.symbol,
            "event_type": event.event_type,
            "sentiment": event.sentiment,
            "confidence": event.confidence,
            "impact_horizon": event.impact_horizon,
            "risk_tags": list(event.risk_tags),
        }
        for event in events
    ]
    return pd.DataFrame(rows)


def build_daily_text_features(events: pd.DataFrame) -> pd.DataFrame:
    """把“逐条新闻事件”聚合成“每日每股票特征”。

    为什么要聚合：
        行情特征通常是一只股票一天一行。
        但新闻可能一天很多条。
        所以要按 date + symbol 聚合，才能和价格特征 merge。

    例：
        AAPL 2024-01-02 有 8 条新闻
        -> 聚合成 1 行 daily_text_features
    """
    if events.empty:
        return pd.DataFrame(columns=["date", "symbol", *TEXT_FEATURE_COLUMNS])

    frame = events.copy()

    # weighted_sentiment 是“带置信度权重的情绪”。
    # 例：sentiment=-0.6, confidence=0.9 -> -0.54，影响较大。
    #     sentiment=-0.6, confidence=0.3 -> -0.18，影响较小。
    frame["weighted_sentiment"] = frame["sentiment"] * frame["confidence"]

    # 把类别字段转成 0/1 数字，机器学习模型才能直接使用。
    frame["event_earnings"] = (frame["event_type"] == "earnings").astype(int)
    frame["event_macro"] = (frame["event_type"] == "macro").astype(int)

    # risk_tags 是 list/tuple；如果包含某个标签，就记 1，否则记 0。
    frame["risk_margin_pressure"] = frame["risk_tags"].apply(lambda tags: int("margin_pressure" in tags))
    frame["risk_guidance_weak"] = frame["risk_tags"].apply(lambda tags: int("guidance_weak" in tags))
    frame["risk_supply_chain"] = frame["risk_tags"].apply(lambda tags: int("supply_chain" in tags))

    # groupby(["date", "symbol"]) 表示：同一天、同一只股票的所有新闻聚合到一行。
    grouped = frame.groupby(["date", "symbol"], as_index=False).agg(
        llm_news_count=("sentiment", "size"),
        llm_mean_sentiment=("sentiment", "mean"),
        llm_weighted_sentiment=("weighted_sentiment", "mean"),
        llm_max_confidence=("confidence", "max"),
        event_earnings_count=("event_earnings", "sum"),
        event_macro_count=("event_macro", "sum"),
        risk_margin_pressure_count=("risk_margin_pressure", "sum"),
        risk_guidance_weak_count=("risk_guidance_weak", "sum"),
        risk_supply_chain_count=("risk_supply_chain", "sum"),
    )
    return grouped


def join_text_features(price_features: pd.DataFrame, text_features: pd.DataFrame) -> pd.DataFrame:
    """把每日文本特征拼到价格特征上。

    price_features:
        一只股票一天一行，包含 ret_1d/vol_20d/ma_gap_10d 等价格特征。

    text_features:
        一只股票一天一行，包含 llm_mean_sentiment/risk_* 等文本特征。

    how="left"：
        保留所有价格行。没有新闻的日期，文本特征填 0。
        这样模型可以理解“今天没有相关新闻”也是一种状态。
    """
    merged = price_features.merge(text_features, on=["date", "symbol"], how="left")

    # 没有新闻的日期，merge 后文本列是 NaN。
    # 填 0 表示：新闻数量 0、情绪 0、风险计数 0。
    for column in TEXT_FEATURE_COLUMNS:
        merged[column] = merged[column].fillna(0.0)
    return merged
