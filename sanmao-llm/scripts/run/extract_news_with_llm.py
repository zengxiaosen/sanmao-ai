from __future__ import annotations

import argparse
import pandas as pd

from quant_llm.config import load_project_env
from quant_llm.llm_extractor import AnthropicLLMExtractor, DEFAULT_ANTHROPIC_MODEL, event_to_dict
from quant_llm.text_features import RuleBasedTextExtractor, extract_text_events, load_news_csv


def main() -> int:
    # 这个脚本的定位：
    #   输入：news CSV，至少包含 date/symbol/title/body 四列。
    #   处理：逐条新闻调用“文本抽取器”，把自然语言转成结构化事件字段。
    #   输出：events CSV，字段包括 event_type/sentiment/confidence/impact_horizon/risk_tags。
    #
    # 为什么单独做这个脚本：
    #   1. LLM 推理有成本（API 调用费 + 网络延迟），应该先离线抽取并保存结果。
    #   2. 下游训练/回测只读结构化 CSV，不需要每次重新调用大模型。
    #   3. 抽取器默认走 Claude API；输出 schema 保持一致，方便以后换模型或换 provider。
    parser = argparse.ArgumentParser(description="Extract financial text events from news CSV using Claude API or rule fallback.")
    parser.add_argument("--news-csv", required=True, help="输入新闻 CSV 路径，必须有 date/symbol/title/body 四列。")
    parser.add_argument("--output", required=True, help="输出结构化事件 CSV 路径。")
    parser.add_argument(
        "--model",
        default=DEFAULT_ANTHROPIC_MODEL,
        help=f"Claude 模型名，默认 {DEFAULT_ANTHROPIC_MODEL}（便宜、快，适合批量抽取）。质量优先可换 claude-sonnet-5 或 claude-opus-4-8。",
    )
    parser.add_argument("--limit", type=int, default=0, help="只处理前 N 条新闻，调试时建议先设小一点，避免一次性花很多 API 调用。")
    parser.add_argument("--rule-fallback-only", action="store_true", help="不调用大模型，只用规则抽取器跑通流程（无需 API key/网络）。")
    args = parser.parse_args()

    # 读取项目 .env，例如 ANTHROPIC_API_KEY、TIINGO_API_KEY。
    # AnthropicLLMExtractor 依赖 ANTHROPIC_API_KEY，SDK 会自动从环境变量读取。
    load_project_env()

    # load_news_csv 会做基础校验：缺 date/symbol/title/body 会直接报错。
    news = load_news_csv(args.news_csv)
    if args.limit:
        # LLM 调用有成本。开发调试时先 limit=3/10，确认输出格式对了再全量跑。
        news = news.head(args.limit)

    if args.rule_fallback_only:
        # 规则抽取器不是真的 LLM，只是用关键词模拟同样的输出格式。
        # 用途：没有 API key/网络时也能测试下游特征、训练、回测链路。
        events = extract_text_events(news, RuleBasedTextExtractor())
    else:
        # AnthropicLLMExtractor 是 Claude API 封装层。
        # 它会：
        #   1. 为每条新闻构造 prompt。
        #   2. 调用 Claude messages API（structured outputs 保证 JSON schema）。
        #   3. 解析并清洗 JSON，返回 TextEvent；失败自动 fallback 到规则抽取器。
        extractor = AnthropicLLMExtractor(model=args.model)

        # iterrows 逐条处理，逻辑最容易看懂。后续数据量大时，可以改批处理
        # （Anthropic Batches API）或并发，但第一版先保证正确和可解释。
        rows = [event_to_dict(extractor.extract(row)) for _, row in news.iterrows()]
        events = pd.DataFrame(rows)

    # 输出 CSV 是为了让下游 pipeline 可以复用结果，不必每次训练都重新跑 LLM。
    events.to_csv(args.output, index=False)
    print(f"saved {len(events)} extracted events to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
