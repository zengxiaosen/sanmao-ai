from __future__ import annotations

import argparse
import pandas as pd

from quant_llm.config import load_project_env
from quant_llm.llm_extractor import TransformersLLMExtractor, event_to_dict
from quant_llm.text_features import RuleBasedTextExtractor, extract_text_events, load_news_csv


def main() -> int:
    # 这个脚本的定位：
    #   输入：news CSV，至少包含 date/symbol/title/body 四列。
    #   处理：逐条新闻调用“文本抽取器”，把自然语言转成结构化事件字段。
    #   输出：events CSV，字段包括 event_type/sentiment/confidence/impact_horizon/risk_tags。
    #
    # 为什么单独做这个脚本：
    #   1. LLM 推理很慢、很贵，应该先离线抽取并保存结果。
    #   2. 下游训练/回测只读结构化 CSV，不需要每次重新调用大模型。
    #   3. 以后可以替换成 vLLM/API LLM，但输出 schema 保持一致。
    parser = argparse.ArgumentParser(description="Extract financial text events from news CSV using local LLM or rule fallback.")
    parser.add_argument("--news-csv", required=True, help="输入新闻 CSV 路径，必须有 date/symbol/title/body 四列。")
    parser.add_argument("--output", required=True, help="输出结构化事件 CSV 路径。")
    parser.add_argument("--model-path", default="", help="本地 Hugging Face 模型目录。这个参数保留给旧 extractor 兼容链路，不再推荐把 qwen3-8b-awq 当默认主线。")
    parser.add_argument("--limit", type=int, default=0, help="只处理前 N 条新闻，调试大模型时建议先设小一点。")
    parser.add_argument("--rule-fallback-only", action="store_true", help="不调用大模型，只用规则抽取器跑通流程。")
    args = parser.parse_args()

    # 读取项目 .env，例如 TIINGO_API_KEY。这个脚本本身不一定用行情 token，
    # 但保持统一入口，后续如果 LLM/API 需要环境变量，可以直接复用。
    load_project_env()

    # load_news_csv 会做基础校验：缺 date/symbol/title/body 会直接报错。
    news = load_news_csv(args.news_csv)
    if args.limit:
        # LLM 推理成本高。开发调试时先 limit=3/10，确认输出格式对了再全量跑。
        news = news.head(args.limit)

    if args.rule_fallback_only:
        # 规则抽取器不是真的 LLM，只是用关键词模拟同样的输出格式。
        # 用途：没有 GPU/模型时也能测试下游特征、训练、回测链路。
        events = extract_text_events(news, RuleBasedTextExtractor())
    else:
        if not args.model_path:
            raise ValueError("--model-path is required unless --rule-fallback-only is set")

        # TransformersLLMExtractor 是本地大模型封装层。
        # 它会：
        #   1. 从 model_path 加载 tokenizer 和模型权重。
        #   2. 为每条新闻构造 prompt。
        #   3. 调用 model.generate 生成 JSON。
        #   4. 解析并清洗 JSON，返回 TextEvent。
        extractor = TransformersLLMExtractor(args.model_path)

        # iterrows 逐条处理，逻辑最容易看懂。后续数据量大时，可以改批处理、
        # 多进程或 vLLM 服务化，但第一版先保证正确和可解释。
        rows = [event_to_dict(extractor.extract(row)) for _, row in news.iterrows()]
        events = pd.DataFrame(rows)

    # 输出 CSV 是为了让下游 pipeline 可以复用结果，不必每次训练都重新跑 LLM。
    events.to_csv(args.output, index=False)
    print(f"saved {len(events)} extracted events to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
