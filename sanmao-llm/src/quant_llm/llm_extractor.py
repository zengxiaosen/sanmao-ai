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
# /no_think 是 Qwen3 的控制指令：让模型不要输出 <think> 推理过程。
# 如果不加这个，Qwen3 容易先输出解释文本，导致 JSON 解析失败。
SYSTEM_PROMPT = """/no_think
You are a financial information extraction engine.
Return exactly one compact JSON object and nothing else. Do not explain. Do not use markdown.

Return JSON with keys: event_type, sentiment, confidence, impact_horizon, risk_tags.
event_type must be one of: earnings, macro, product, management, legal, supply_chain, other.
sentiment must be a number from -1 to 1.
confidence must be a number from 0 to 1.
confidence means extraction reliability, not the probability that the stock will rise.
Use confidence around 0.85-0.95 only when the text clearly names the company, event, direction, and risk.
Use confidence around 0.55-0.75 when the event is relevant but mixed, vague, or partly implied.
Use confidence around 0.20-0.50 when the ticker link or financial impact is weak or uncertain.
impact_horizon must be one of: intraday, 1-5d, 1-20d, long_term.
risk_tags must be an array of strings."""


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
    """把一条新闻拼成 LLM prompt。

    参数：
        title: 新闻标题。
        body: 新闻正文或摘要。
        symbol: 股票代码，例如 AAPL.US。

    返回：
        给 Qwen/其他 LLM 的完整文本指令。

    输出要求在 SYSTEM_PROMPT 里已经固定：只能返回 JSON。
    """
    return f"""{SYSTEM_PROMPT}

Symbol: {symbol}
Title: {title}
Text: {body}

JSON:"""


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


class TransformersLLMExtractor:
    """本地 Hugging Face LLM 抽取器。

    这个类是项目里真正调用 Qwen 的地方。

    为什么把 transformers import 放在 __init__ 里面：
        量化主流程不应该强依赖 LLM 推理库。
        如果只是跑价格特征/回测，不需要安装 transformers/autoawq。

    和 RuleBasedTextExtractor 的关系：
        - RuleBasedTextExtractor：关键词规则，便宜、稳定、但不聪明。
        - TransformersLLMExtractor：本地大模型，能理解文本，但更慢、更依赖 GPU。

    两者输出都转成 TextEvent，所以下游特征工程不用关心来源。
    """

    def __init__(self, model_path: str, max_new_tokens: int = 192) -> None:
        from transformers import AutoModelForCausalLM, AutoTokenizer

        # tokenizer 负责把 prompt 文本转成 token id，也负责把模型输出 token 解码回文本。
        self.tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)

        # model 是真正的本地大模型。
        # device_map="auto" 会让 transformers 自动把模型放到 GPU/CPU 合适位置。
        # Qwen3-8B-AWQ 在 48GB 显存上可以直接加载。
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            device_map="auto",
            trust_remote_code=True,
        )

        # 限制最多生成多少 token，避免模型啰嗦输出很长文本。
        # 这里输出一个短 JSON 足够，不需要几千 token。
        self.max_new_tokens = max_new_tokens

    def extract(self, row: pd.Series) -> TextEvent:
        """对单条新闻做 LLM 结构化抽取。

        输入 row 至少要有：
            title/body/symbol/date

        输出 TextEvent：
            date, symbol, event_type, sentiment, confidence, impact_horizon, risk_tags
        """
        prompt = build_extraction_prompt(str(row.get("title", "")), str(row.get("body", "")), str(row.get("symbol", "")))
        messages = [{"role": "user", "content": prompt}]

        # 对 Qwen 这类 chat model，最好用模型自带 chat template。
        # enable_thinking=False 是 Qwen3 的关键参数：关闭思考文本，只要最终 JSON。
        if hasattr(self.tokenizer, "apply_chat_template"):
            try:
                text = self.tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                    enable_thinking=False,
                )
            except TypeError:
                text = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        else:
            text = prompt

        # 把 prompt 转成模型输入，并移动到模型所在设备。
        inputs = self.tokenizer(text, return_tensors="pt").to(self.model.device)

        # do_sample=False 表示确定性生成：同样输入尽量得到同样输出。
        # temperature/top_p/top_k 设为 None，是为了避免 generation_config 里的采样参数干扰。
        output_ids = self.model.generate(
            **inputs,
            max_new_tokens=self.max_new_tokens,
            do_sample=False,
            temperature=None,
            top_p=None,
            top_k=None,
            pad_token_id=self.tokenizer.eos_token_id,
        )

        # output_ids 包含“输入 prompt + 新生成内容”。
        # inputs["input_ids"].shape[-1] 是输入长度，切掉前半段，只保留模型新生成的 JSON。
        generated = self.tokenizer.decode(output_ids[0][inputs["input_ids"].shape[-1] :], skip_special_tokens=True)
        try:
            return parse_llm_event_json(generated, row)
        except Exception:
            # 大模型有时仍可能输出坏 JSON。为了让批处理不中断，这里 fallback 到规则抽取器。
            # 注意：生产阶段应该把失败样本记录到日志，方便人工检查和改 prompt。
            return RuleBasedTextExtractor().extract(row)


def event_to_dict(event: TextEvent) -> dict:
    """把 TextEvent dataclass 转成可写入 CSV/Parquet 的 dict。"""
    row = asdict(event)

    # TextEvent 里 risk_tags 是 tuple，写 CSV/JSON 前转成 list 更直观。
    row["risk_tags"] = list(event.risk_tags)
    return row
