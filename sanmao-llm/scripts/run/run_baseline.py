from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import joblib
import pandas as pd

from quant_llm.backtest import build_backtest_frames, summarize_backtest
from quant_llm.config import load_config, load_project_env
from quant_llm.data import apply_universe_membership, load_price_panel, load_universe_membership
from quant_llm.features import FEATURE_COLUMNS, build_price_features
from quant_llm.factor_analytics import (
    detect_factor_decay,
    factor_importance_timeline,
    return_attribution,
    rolling_factor_betas,
    suggest_replacements,
)
from quant_llm.macro import (
    MACRO_FEATURE_COLUMNS,
    build_macro_features,
    fetch_macro_panel,
    join_macro_features,
)
from quant_llm.modeling import WalkForwardConfig, fit_final_model, walk_forward_predict
from quant_llm.paths import build_run_identity, resolve_model_dir, validate_artifact_isolation
from quant_llm.regime import detect_regimes, factor_regime_performance
from quant_llm.review import build_review, render_review_markdown
from quant_llm.text_features import (
    TEXT_FEATURE_COLUMNS,
    build_daily_text_features,
    extract_text_events,
    join_text_features,
    load_news_csv,
    load_text_events_csv,
)


def duckdb_string_literal(value: str) -> str:
    """把 Python 字符串安全放进 DuckDB SQL。

    这里主要用于 parquet 文件路径。
    如果路径里有单引号，需要替换成两个单引号，避免 SQL 语法错误。
    """
    return "'" + value.replace("'", "''") + "'"


def passes_model_promotion_gate(backtest: dict, promotion_config: dict | None) -> tuple[bool, list[str]]:
    """判断候选模型能不能晋级为 latest_model。

    这里的 gate 不是“自动调参”，只是最基本的安全门槛：
    先回测，再决定是否把本次候选模型覆盖成 latest_model.joblib。

    为什么需要这个函数：
      1. walk-forward 回测用来评估策略历史表现。
      2. fit_final_model 会用全部训练样本训练一个 candidate_model，供后续模拟盘使用。
      3. 如果回测明显很差，就不应该让 candidate 自动覆盖 latest_model。

    返回：
      promoted:
        True 表示通过门槛，可以覆盖 latest_model。
        False 表示只保存 candidate_model，不覆盖 latest_model。

      reasons:
        人能读懂的原因，会写进 metrics.json。
    """
    promotion_config = promotion_config or {}
    if not promotion_config.get("enabled", False):
        return True, ["model_promotion.enabled=false_or_missing: backward compatible auto-promotion"]

    checks = [
        ("annual_return", promotion_config.get("min_annual_return"), ">="),
        ("sharpe", promotion_config.get("min_sharpe"), ">="),
        ("max_drawdown", promotion_config.get("min_max_drawdown"), ">="),
        ("mean_daily_turnover", promotion_config.get("max_mean_daily_turnover"), "<="),
    ]

    reasons: list[str] = []
    promoted = True
    for metric_name, threshold, operator in checks:
        if threshold is None:
            continue
        actual = backtest.get(metric_name)
        if actual is None:
            promoted = False
            reasons.append(f"{metric_name}: missing, required {operator} {threshold}")
            continue

        if operator == ">=":
            passed = float(actual) >= float(threshold)
        else:
            passed = float(actual) <= float(threshold)

        status = "PASS" if passed else "FAIL"
        reasons.append(f"{metric_name}: {actual:.6f} {operator} {threshold} [{status}]")
        if not passed:
            promoted = False

    if not reasons:
        reasons.append("model_promotion.enabled=true but no thresholds configured")
    return promoted, reasons


def main() -> int:
    # run_baseline.py 是当前最核心的量化研究入口。
    #
    # 它做的事情按顺序是：
    #   1. 读取 YAML 配置。
    #   2. 拉取/读取市场价格数据。
    #   3. 生成价格特征，例如 ret_1d、vol_20d。
    #   4. 如果配置打开 text_features，就读取新闻并生成文本特征。
    #   5. 把价格特征和文本特征拼成训练样本。
    #   6. walk-forward 训练模型并输出 prob_up。
    #   7. 根据 prob_up 做 long/flat 回测。
    #   8. 保存 parquet、metrics.json 和 DuckDB view。
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    # 读取 .env，例如 TIINGO_API_KEY。
    load_project_env()

    # YAML 配置里定义股票池、日期、数据源、模型参数、回测阈值等。
    config = load_config(args.config)

    # data_dir 保存中间数据，report_dir 保存预测和指标。
    # model_dir 必须按 strategy_id 隔离，不能让美股/A 股/港股共用同一个 latest_model.joblib。
    data_dir = Path(config["data_dir"])
    report_dir = Path(config["report_dir"])
    feature_dir = data_dir / "features"
    model_dir = resolve_model_dir(config, data_dir, args.config)
    run_identity = build_run_identity(config, args.config)
    validate_artifact_isolation(
        config,
        data_dir=data_dir,
        report_dir=report_dir,
        model_dir=model_dir,
        config_path=args.config,
    )
    report_dir.mkdir(parents=True, exist_ok=True)
    feature_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)

    # 第一步：加载市场行情。
    # 输出 prices 是长表格式：date/symbol/open/high/low/close/volume...
    prices = load_price_panel(
        config["symbols"],
        config["start_date"],
        config["end_date"],
        data_dir,
        allow_synthetic_fallback=config.get("allow_synthetic_fallback", False),
        provider=config.get("market_data_provider", "yfinance"),
    )
    if config.get("universe_membership_csv"):
        membership = load_universe_membership(config["universe_membership_csv"])
        prices = apply_universe_membership(prices, membership)

    # 第二步：从价格生成机器学习特征。
    # 例如：过去 1/5/20 日收益、20 日波动率、均线偏离、成交量 z-score。
    # 同时生成 target_up：未来 N 天是否上涨。
    features = build_price_features(prices, horizon_days=config["prediction_horizon_days"])

    # feature_columns 是最终喂给模型的列名列表。
    # 先放价格特征；如果开启文本特征，后面再 append TEXT_FEATURE_COLUMNS。
    feature_columns = list(FEATURE_COLUMNS)
    text_events = None
    daily_text_features = None
    training_features = features

    # 第三步：可选文本特征。
    #
    # 支持两种输入：
    #   A. news_csv：原始文本 CSV，包含 date/symbol/title/body。
    #      run_baseline.py 会在这里用 RuleBasedTextExtractor 临时抽取。
    #
    #   B. events_csv：已经抽取好的结构化事件 CSV，包含
    #      date/symbol/event_type/sentiment/confidence/impact_horizon/risk_tags。
    #      这是 Qwen 链路推荐方式：run_all.sh 先确保 events_csv 存在，
    #      run_baseline.py 再直接读取它训练，不需要你手工分两步跑。
    text_config = config.get("text_features", {})
    if text_config.get("enabled", False):
        if text_config.get("events_csv"):
            # Qwen/LLM 模式：直接读取已抽取好的事件文件。
            # 这样训练时不会重复调用大模型，速度更稳定，也方便复现实验。
            text_events = load_text_events_csv(text_config["events_csv"])
        else:
            # 规则 baseline 模式：读取原始新闻/公告，再用规则抽取器生成事件。
            # 这个路径适合 smoke test 或没有 GPU/LLM 的机器。
            news = load_news_csv(text_config["news_csv"])
            text_events = extract_text_events(news)

        # 这里的 news_csv/events_csv 来自配置文件，不是脚本硬编码。
        # 以 config/sec_filings_baseline.yaml 为例：
        #   text_features.news_csv:
        #     /root/sanmao-ai/sanmao-llm/data/us_sec_rule_text_xgboost_v1/news/sec_filings.csv
        # 以 config/sec_filings_qwen.yaml 为例：
        #   text_features.events_csv:
        #     /root/sanmao-ai/sanmao-llm/data/us_sec_qwen_xgboost_v1/news/sec_filings_qwen_events.csv
        daily_text_features = build_daily_text_features(text_events)

        # join_text_features 会按 date + symbol 把文本特征拼到价格特征上。
        # 没有新闻的日期，文本特征填 0。
        # 这是 pandas DataFrame merge，不是往数据库表追加列。
        # 合并结果之后保存到 training_features.parquet。
        training_features = join_text_features(features, daily_text_features)
        feature_columns.extend(TEXT_FEATURE_COLUMNS)

    # 第三步·补充：可选宏观因子（macro）。
    #
    # 宏观因子是“整个市场共享”的大环境指标（VIX 恐慌指数、10年美债收益率、美元指数），
    # 影响所有股票，尤其压制高估值科技股。它让因子库从“量价+舆情”补齐到三大类。
    #
    # 配置示例（config 里加）：
    #   macro:
    #     enabled: true
    # 数据靠 yfinance 拉 ^VIX/^TNX/DX-Y.NYB，无网/限流时按 date 填 0，不影响主链路。
    macro_config = config.get("macro", {})
    macro_features = None
    if macro_config.get("enabled", False):
        macro_panel = fetch_macro_panel(
            config["start_date"],
            config["end_date"],
            data_dir,
            allow_synthetic_fallback=config.get("allow_synthetic_fallback", False),
        )
        macro_features = build_macro_features(macro_panel)
        # 宏观只按 date merge（不分股票）。拼到当前 training_features 上。
        training_features = join_macro_features(training_features, macro_features)
        feature_columns.extend(MACRO_FEATURE_COLUMNS)

    # 第四步：walk-forward 训练和预测。
    # walk-forward 的含义：
    #   用过去一段时间训练 -> 预测未来一小段 -> 窗口向前滚动。
    # 这样比随机切分更接近真实交易，因为未来数据不会泄露到过去。
    predictions, fold_metrics = walk_forward_predict(
        training_features,
        WalkForwardConfig(
            train_window_days=config["train_window_days"],
            test_window_days=config["test_window_days"],
            min_train_rows=config["min_train_rows"],
        ),
        config["model"],
        feature_columns,
    )

    # 第五步：把预测概率 prob_up 转成策略收益。
    # long_flat_backtest 规则：
    #   prob_up >= threshold -> long，持有股票
    #   prob_up < threshold  -> flat，空仓
    # 仓位变化时会扣 transaction cost。
    backtest_positions, backtest_daily = build_backtest_frames(
        predictions,
        threshold=config["probability_threshold"],
        transaction_cost_bps=config["transaction_cost_bps"],
    )
    backtest = summarize_backtest(backtest_daily, backtest_positions)

    # 第六步：训练一个“候选模型”给后续模拟盘/应用加载。
    #
    # 注意区分：
    #   walk-forward 里的模型：历史窗口临时训练，只用于评估。
    #   candidate_model：用当前全部 training_features 重新训练，保存到磁盘。
    #
    # 为什么还要重新训练一次：
    #   walk-forward 过程中会产生多个临时模型，每个模型只看自己那个历史窗口；
    #   它们是评估工具，不是一个统一的、可部署的模型文件。
    #   如果策略评估通过，就需要用同一套参数和全部已有样本训练一个候选模型，
    #   这样后续 paper trading 才能加载一个确定的 joblib 文件。
    #
    # 这不是自动优化：模型参数没有因为回测结果被自动改动。
    candidate_model = fit_final_model(training_features, config["model"], feature_columns)
    promoted, promotion_reasons = passes_model_promotion_gate(backtest, config.get("model_promotion"))

    # 第六步·补充：可选因子有效性分析（课题 AI 工作流核心）。
    #
    # 打开模型黑盒：
    #   - 因子重要性时间线：模型每个窗口最看重哪些因子（随时间变化）。
    #   - 滚动回归 beta/t：每个因子和未来收益的关系强不强、还成立吗。
    #   - 失效检测 + 替换：哪些因子在衰退/失效，用同类里的健康因子替换。
    #   - 收益归因：把预期收益拆成各因子的贡献。
    #
    # 配置示例：
    #   factor_analytics:
    #     enabled: true
    #     beta_window: 60
    factor_config = config.get("factor_analytics", {})
    fa_importance = fa_betas = fa_decay = fa_replacements = fa_attribution = None
    if factor_config.get("enabled", False):
        wf = WalkForwardConfig(
            train_window_days=config["train_window_days"],
            test_window_days=config["test_window_days"],
            min_train_rows=config["min_train_rows"],
        )
        fa_importance = factor_importance_timeline(training_features, wf, config["model"], feature_columns)
        fa_betas = rolling_factor_betas(training_features, feature_columns, window=factor_config.get("beta_window", 60))
        # coverage：每个因子的非零天数占比。事件类因子（公告计数）大多数日子是 0，
        # 样本太稀疏时不能下“衰退/失效”结论，detect_factor_decay 会标成 sparse。
        factor_coverage = {
            c: float((pd.to_numeric(training_features[c], errors="coerce").fillna(0.0) != 0).mean())
            for c in feature_columns
        }
        fa_decay = detect_factor_decay(fa_importance, fa_betas, coverage=factor_coverage)
        # 因子分组：量价 + 舆情（若启用）+ 宏观（若启用）。用于同类替换。
        groups = {"price_volume": list(FEATURE_COLUMNS)}
        if text_config.get("enabled", False):
            groups["sentiment"] = list(TEXT_FEATURE_COLUMNS)
        if macro_config.get("enabled", False):
            groups["macro"] = list(MACRO_FEATURE_COLUMNS)
        fa_replacements = suggest_replacements(fa_decay, groups)
        fa_attribution = return_attribution(predictions, training_features, fa_betas, feature_columns)

    # 第六步·补充2：可选市场状态识别（P4 regime）。
    #
    # 把每天标注成 bull/bear/high_vol/sideways 四种状态，
    # 并统计每个因子在每种状态下的表现 —— 支撑“因子有效性随市场状态切换”的展示。
    # 配置示例：
    #   regime:
    #     enabled: true
    regime_config = config.get("regime", {})
    regimes = None
    regime_perf = None
    if regime_config.get("enabled", False):
        regimes = detect_regimes(
            features,
            macro_features,
            trend_window=regime_config.get("trend_window", 60),
            trend_threshold=regime_config.get("trend_threshold", 0.08),
            vix_threshold=regime_config.get("vix_threshold", 25.0),
        )
        if fa_betas is not None and not fa_betas.empty:
            regime_perf = factor_regime_performance(fa_betas, regimes)

    prices_path = feature_dir / "prices.parquet"
    features_path = feature_dir / "price_features.parquet"
    training_features_path = feature_dir / "training_features.parquet"
    predictions_path = report_dir / "predictions.parquet"
    backtest_daily_path = report_dir / "backtest_daily.parquet"
    backtest_daily_csv_path = report_dir / "backtest_daily.csv"
    backtest_positions_path = report_dir / "backtest_positions.parquet"
    latest_signals_path = report_dir / "latest_signals.csv"
    metrics_path = report_dir / "metrics.json"
    candidate_model_path = model_dir / "candidate_model.joblib"
    candidate_model_metadata_path = model_dir / "candidate_model_metadata.json"
    latest_model_path = model_dir / "latest_model.joblib"
    latest_model_metadata_path = model_dir / "latest_model_metadata.json"
    db_path = data_dir / "quant.duckdb"

    # 第七步：保存中间结果和直观报告。
    # parquet 是适合表格数据的列式文件格式，比 CSV 更适合后续反复读取。
    prices.to_parquet(prices_path, index=False)
    features.to_parquet(features_path, index=False)

    # training_features.parquet:
    #   最终训练表。这里已经同时包含价格特征和文本特征。
    training_features.to_parquet(training_features_path, index=False)
    if text_events is not None and daily_text_features is not None:
        # text_events.parquet:
        #   一条文本/公告一行，保留 event_type/sentiment/confidence/risk_tags。
        text_events.to_parquet(feature_dir / "text_events.parquet", index=False)

        # daily_text_features.parquet:
        #   按 date+symbol 聚合后一行，方便和价格特征拼接。
        daily_text_features.to_parquet(feature_dir / "daily_text_features.parquet", index=False)

    # predictions.parquet:
    #   walk-forward 模型输出，包含 prob_up 和真实 forward_return。
    predictions.to_parquet(predictions_path, index=False)

    # backtest_daily:
    #   最直观看收益的文件。包含每日 strategy_ret、equity、drawdown。
    #   equity 从 1.0 起步，1.15 表示累计收益约 +15%。
    backtest_daily.to_parquet(backtest_daily_path, index=False)
    backtest_daily.to_csv(backtest_daily_csv_path, index=False)

    # backtest_positions:
    #   每只股票每天的 prob_up、position、turnover、strategy_ret。
    #   想看某天为什么持仓/空仓，看这个文件。
    backtest_positions.to_parquet(backtest_positions_path, index=False)

    # latest_signals:
    #   取回测预测结果中最新一天的每个 symbol 信号。
    #   这不是实盘订单，只是给模拟盘/下一步应用的“信号样例”。
    latest_date = predictions["date"].max()
    latest_signals = backtest_positions.loc[backtest_positions["date"] == latest_date].copy()
    latest_signals["action"] = latest_signals["position"].map({1.0: "long", 0.0: "flat"})
    latest_signals[["date", "symbol", "close", "prob_up", "position", "action"]].to_csv(latest_signals_path, index=False)

    # 因子有效性分析产物（P3）。启用 factor_analytics 时才会生成。
    if fa_importance is not None:
        fa_importance.to_parquet(report_dir / "factor_importance_timeline.parquet", index=False)
        fa_betas.to_parquet(report_dir / "rolling_betas.parquet", index=False)
        fa_decay.to_parquet(report_dir / "factor_decay.parquet", index=False)
        fa_replacements.to_parquet(report_dir / "factor_replacements.parquet", index=False)
        fa_attribution.to_parquet(report_dir / "return_attribution.parquet", index=False)

    # 市场状态产物（P4 regime）。
    if regimes is not None:
        regimes.to_parquet(report_dir / "regime_timeline.parquet", index=False)
        if regime_perf is not None:
            regime_perf.to_parquet(report_dir / "factor_regime_performance.parquet", index=False)

    # 自动复盘（P4 review）：把本次运行浓缩成 review.json（看板用）+ review.md（人读）。
    # 配置示例：
    #   review:
    #     enabled: true
    if config.get("review", {}).get("enabled", False):
        signal_rows = latest_signals[["date", "symbol", "close", "prob_up", "position", "action"]].to_dict("records")
        latest_signal = None
        if signal_rows:
            latest_signal = dict(signal_rows[0])
            latest_signal["date"] = str(pd.Timestamp(latest_signal["date"]).date())
        review = build_review(
            backtest_summary=backtest,
            decay_table=fa_decay,
            replacements=fa_replacements,
            regimes=regimes,
            latest_signal=latest_signal,
            importance_timeline=fa_importance,
            data_range=(str(config["start_date"]), str(config["end_date"])),
        )
        (report_dir / "review.json").write_text(
            json.dumps(review, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (report_dir / "review.md").write_text(render_review_markdown(review), encoding="utf-8")

    # candidate_model.joblib:
    #   本次运行训练出的候选模型。它一定会保存，方便复盘和比较。
    #   但只有回测指标通过 model_promotion 门槛时，才覆盖 latest_model.joblib。
    joblib.dump(candidate_model, candidate_model_path)

    model_metadata = {
        "market": run_identity["market"],
        "strategy_id": run_identity["strategy_id"],
        "model_dir": str(model_dir),
        "candidate_model_path": str(candidate_model_path),
        "latest_model_path": str(latest_model_path),
        "config_path": args.config,
        "feature_columns": feature_columns,
        "symbols": config["symbols"],
        "trained_rows": len(training_features),
        "trained_start": str(pd.Timestamp(training_features["date"].min()).date()),
        "trained_end": str(pd.Timestamp(training_features["date"].max()).date()),
        "prediction_horizon_days": config["prediction_horizon_days"],
        "probability_threshold": config["probability_threshold"],
        "promoted_to_latest": promoted,
        "promotion_reasons": promotion_reasons,
        "note": (
            "Candidate model trained on all available training_features after walk-forward backtest. "
            "It is promoted to latest_model only if model_promotion gates pass."
        ),
    }
    candidate_model_metadata_path.write_text(json.dumps(model_metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    if promoted:
        # latest_model.joblib:
        #   后续 paper trading / 模拟盘默认加载这个模型。
        #   只有 candidate 通过回测门槛时才覆盖，避免差模型自动晋级。
        joblib.dump(candidate_model, latest_model_path)
        latest_model_metadata_path.write_text(json.dumps(model_metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    # metrics.json 是本次实验报告：样本数、使用特征、每个 walk-forward fold 指标、回测指标。
    metrics = {
        "market": run_identity["market"],
        "strategy_id": run_identity["strategy_id"],
        "model_dir": str(model_dir),
        "symbols": config["symbols"],
        "rows": {
            "prices": len(prices),
            "features": len(features),
            "training_features": len(training_features),
            "predictions": len(predictions),
        },
        "feature_columns": feature_columns,
        "fold_metrics": fold_metrics,
        "backtest": backtest,
        "model_promotion": {
            "promoted_to_latest": promoted,
            "reasons": promotion_reasons,
        },
        "artifacts": {
            "candidate_model": str(candidate_model_path),
            "candidate_model_metadata": str(candidate_model_metadata_path),
            "latest_model": str(latest_model_path) if promoted else None,
            "latest_model_metadata": str(latest_model_metadata_path) if promoted else None,
            "training_features": str(training_features_path),
            "predictions": str(predictions_path),
            "backtest_daily": str(backtest_daily_path),
            "backtest_daily_csv": str(backtest_daily_csv_path),
            "backtest_positions": str(backtest_positions_path),
            "latest_signals": str(latest_signals_path),
            "duckdb": str(db_path),
        },
    }
    metrics_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")

    # DuckDB 是本地分析数据库。
    # 这里不把数据复制进数据库，而是创建 view 指向 parquet 文件。
    # 好处：以后可以用 SQL 快速查询 prices/features/predictions。
    with duckdb.connect(str(db_path)) as con:
        con.execute(f"CREATE OR REPLACE VIEW prices AS SELECT * FROM read_parquet({duckdb_string_literal(str(prices_path))})")
        con.execute(
            f"CREATE OR REPLACE VIEW price_features AS SELECT * FROM read_parquet({duckdb_string_literal(str(features_path))})"
        )
        con.execute(
            f"CREATE OR REPLACE VIEW training_features AS SELECT * FROM read_parquet({duckdb_string_literal(str(training_features_path))})"
        )
        if text_events is not None and daily_text_features is not None:
            con.execute(
                f"CREATE OR REPLACE VIEW text_events AS SELECT * FROM read_parquet({duckdb_string_literal(str(feature_dir / 'text_events.parquet'))})"
            )
            con.execute(
                f"CREATE OR REPLACE VIEW daily_text_features AS SELECT * FROM read_parquet({duckdb_string_literal(str(feature_dir / 'daily_text_features.parquet'))})"
            )
        con.execute(
            f"CREATE OR REPLACE VIEW predictions AS SELECT * FROM read_parquet({duckdb_string_literal(str(predictions_path))})"
        )
        con.execute(
            f"CREATE OR REPLACE VIEW backtest_daily AS SELECT * FROM read_parquet({duckdb_string_literal(str(backtest_daily_path))})"
        )
        con.execute(
            f"CREATE OR REPLACE VIEW backtest_positions AS SELECT * FROM read_parquet({duckdb_string_literal(str(backtest_positions_path))})"
        )

    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
