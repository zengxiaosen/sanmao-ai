from __future__ import annotations

import json
import re
from dataclasses import asdict

import pandas as pd

from quant_llm.text_features import RuleBasedTextExtractor, TextEvent


# SYSTEM_PROMPT 是给大模型看的“抽取说明书”。
#
# 目标不是让 LLM 直接判断买卖，而是让它把新闻/公告文本转成稳定 JSON。
# 下游机器学习模型会再把这些 JSON 字段变成表格特征，和价格特征一起训练。
#
# 当前抽取器走 Claude API（Anthropic SDK），并用 structured outputs 强制 JSON schema，
# 所以这里不再需要 Qwen 专属的 /no_think 之类控制指令。系统提示只负责说明字段语义，
# 输出格式由 EVENT_SCHEMA 保证。
SYSTEM_PROMPT = """You are a financial information extraction engine.
Turn one piece of financial news or filing text into a single structured event.

Field semantics:
- event_type must be one of: earnings, macro, product, management, legal, supply_chain, other.
- sentiment is a number from -1 to 1; negative means bearish, positive means bullish.
- confidence is a number from 0 to 1 and means extraction reliability, NOT the probability that the stock will rise.
  Use confidence around 0.85-0.95 only when the text clearly names the company, event, direction, and risk.
  Use confidence around 0.55-0.75 when the event is relevant but mixed, vague, or partly implied.
  Use confidence around 0.20-0.50 when the ticker link or financial impact is weak or uncertain.
- impact_horizon must be one of: intraday, 1-5d, 1-20d, long_term.
- risk_tags is an array of short risk label strings; use an empty array when no clear risk is present."""


# EVENT_SCHEMA 是给 Claude structured outputs 用的 JSON schema。
# 它保证返回内容一定是符合结构的 JSON，省掉旧链路里“正则抓 JSON + 容错解析”的脆弱步骤。
# 数值范围（sentiment/confidence）JSON schema 不强制，仍由 parse_llm_event_json 里的 _clip 兜底。
EVENT_SCHEMA = {
    "type": "object",
    "properties": {
        "event_type": {
            "type": "string",
            "enum": sorted(["earnings", "macro", "product", "management", "legal", "supply_chain", "other"]),
        },
        "sentiment": {"type": "number"},
        "confidence": {"type": "number"},
        "impact_horizon": {
            "type": "string",
            "enum": sorted(["intraday", "1-5d", "1-20d", "long_term"]),
        },
        "risk_tags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["event_type", "sentiment", "confidence", "impact_horizon", "risk_tags"],
    "additionalProperties": False,
}

# 批量抽新闻属于“分类/抽取”这类简单、量大、对速度和成本敏感的任务，
# 所以默认用 Claude Haiku 4.5。想要更强的抽取质量，可以在命令行传 --model 换成 Sonnet/Opus。
DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5"


# 白名单：LLM 只能输出这些事件类型。
# 如果它胡乱输出 "rumor"、"unknown_event" 等，后面会统一归到 other。
ALLOWED_EVENT_TYPES = {"earnings", "macro", "product", "management", "legal", "supply_chain", "other"}

# 白名单：影响期限只能落在这些桶里，方便后续变成 one-hot 特征。
ALLOWED_IMPACT_HORIZONS = {"intraday", "1-5d", "1-20d", "long_term"}


def _clip(value: float, low: float, high: float) -> float:
    """把数值限制在合法范围内。

    例：
        sentiment 合法范围是 -1 到 1。
        如果 LLM 错输出 2.4，这里会裁剪成 1.0。

    为什么要做：
        LLM 输出不能完全信任。进入训练数据前必须清洗。
    """
    return max(low, min(high, value))


def build_extraction_prompt(title: str, body: str, symbol: str) -> str:
    """把一条新闻拼成给 LLM 的 user 消息。

    参数：
        title: 新闻标题。
        body: 新闻正文或摘要。
        symbol: 股票代码，例如 AAPL.US。

    返回：
        user 消息文本。系统提示（字段语义）和输出格式（JSON schema）分别由
        SYSTEM_PROMPT 和 EVENT_SCHEMA 负责，所以这里只提供待抽取的原始内容。
    """
    return f"""Symbol: {symbol}
Title: {title}
Text: {body}"""


def parse_llm_event_json(text: str, row: pd.Series) -> TextEvent:
    """解析 LLM 返回的 JSON，并转换成 TextEvent。

    LLM 理想输出：
        {"event_type":"earnings","sentiment":0.3,"confidence":0.85,...}

    实际情况：
        LLM 偶尔会在 JSON 前后加解释文字，或者输出越界数值。
        所以这里做三件事：
          1. 用正则从返回文本里抓第一个 JSON 对象。
          2. 把 risk_tags 统一成 list/tuple。
          3. 校验类别字段，裁剪 sentiment/confidence 数值范围。

    row:
        原始新闻行，用来补 date/symbol。LLM 不负责决定日期和股票代码，
        避免它把 AAPL/Apple 之类实体联错。
    """
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in LLM output: {text[:300]}")

    # json.loads 会把 JSON 字符串转成 Python dict。
    # 如果 LLM 输出的 JSON 格式不合法，这里会抛异常，然后上层 fallback 到规则抽取器。
    payload = json.loads(match.group(0))

    # risk_tags 应该是数组，例如 ["margin_pressure"]。
    # 如果模型误输出字符串 "margin_pressure"，这里也转成单元素数组。
    risk_tags = payload.get("risk_tags") or []
    if not isinstance(risk_tags, list):
        risk_tags = [str(risk_tags)]

    # LLM output is treated as untrusted data. We normalize categories and clip
    # numeric ranges before these fields become model features.
    event_type = str(payload.get("event_type", "other"))
    if event_type not in ALLOWED_EVENT_TYPES:
        event_type = "other"
    impact_horizon = str(payload.get("impact_horizon", "1-5d"))
    if impact_horizon not in ALLOWED_IMPACT_HORIZONS:
        impact_horizon = "1-5d"

    return TextEvent(
        date=pd.Timestamp(row["date"]).normalize(),
        symbol=str(row["symbol"]),
        event_type=event_type,
        sentiment=_clip(float(payload.get("sentiment", 0.0)), -1.0, 1.0),
        confidence=_clip(float(payload.get("confidence", 0.5)), 0.0, 1.0),
        impact_horizon=impact_horizon,
        risk_tags=tuple(str(tag) for tag in risk_tags),
    )


class AnthropicLLMExtractor:
    """基于 Claude API 的文本抽取器。

    这个类是项目里真正调用大模型的地方。它用 Anthropic 官方 SDK 调 Claude，
    不需要本地 GPU、不下载模型权重，只依赖一个 ANTHROPIC_API_KEY。

    为什么把 anthropic import 放在 __init__ 里面：
        量化主流程（价格特征/训练/回测）不应该强依赖 LLM SDK。
        只有真的要跑文本抽取时，才需要安装 anthropic。

    和 RuleBasedTextExtractor 的关系：
        - RuleBasedTextExtractor：关键词规则，便宜、稳定、但不聪明。
        - AnthropicLLMExtractor：调用 Claude，能理解文本，需要 API key 和网络。

    两者输出都转成 TextEvent，所以下游特征工程不用关心来源。

    为什么用 structured outputs：
        通过 output_config.format 传入 EVENT_SCHEMA，Claude 会保证返回严格符合 schema 的 JSON，
        省掉旧本地模型链路里“可能输出解释文本 / 坏 JSON”的问题。数值范围仍由 _clip 兜底。
    """

    def __init__(self, model: str = DEFAULT_ANTHROPIC_MODEL, max_tokens: int = 512) -> None:
        import anthropic

        # 默认构造函数会自动从环境变量读取凭据（ANTHROPIC_API_KEY），
        # 所以不要在代码里硬编码 key。参见 .env.example。
        self.client = anthropic.Anthropic()
        self.model = model

        # 一个短 JSON 事件足够，不需要很大的输出预算。
        self.max_tokens = max_tokens

    def extract(self, row: pd.Series) -> TextEvent:
        """对单条新闻做 LLM 结构化抽取。

        输入 row 至少要有：
            title/body/symbol/date

        输出 TextEvent：
            date, symbol, event_type, sentiment, confidence, impact_horizon, risk_tags
        """
        prompt = build_extraction_prompt(str(row.get("title", "")), str(row.get("body", "")), str(row.get("symbol", "")))

        try:
            # output_config.format 用 json_schema 约束返回结构；structured outputs 保证
            # 第一个 text block 就是合法 JSON。system 传字段语义，user 传待抽取内容。
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
                output_config={"format": {"type": "json_schema", "schema": EVENT_SCHEMA}},
            )
            generated = next(block.text for block in response.content if block.type == "text")
            return parse_llm_event_json(generated, row)
        except Exception:
            # 网络错误、限流、API 拒绝或极少数坏 JSON 都可能发生。为了让批处理不中断，
            # 这里 fallback 到规则抽取器。
            # 注意：生产阶段应该把失败样本记录到日志，方便人工检查和改 prompt。
            return RuleBasedTextExtractor().extract(row)


def event_to_dict(event: TextEvent) -> dict:
    """把 TextEvent dataclass 转成可写入 CSV/Parquet 的 dict。"""
    row = asdict(event)

    # TextEvent 里 risk_tags 是 tuple，写 CSV/JSON 前转成 list 更直观。
    row["risk_tags"] = list(event.risk_tags)
    return row
