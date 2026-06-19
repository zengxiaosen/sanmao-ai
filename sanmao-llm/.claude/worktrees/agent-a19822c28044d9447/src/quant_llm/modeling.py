from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, log_loss, roc_auc_score


@dataclass(frozen=True)
class WalkForwardConfig:
    train_window_days: int
    test_window_days: int
    min_train_rows: int


def make_classifier(model_config: dict):
    kind = model_config.get("kind", "xgboost")
    if kind == "xgboost":
        try:
            from xgboost import XGBClassifier

            return XGBClassifier(
                # Conservative baseline values: enough trees to learn, shallow depth to reduce overfit.
                n_estimators=model_config.get("n_estimators", 200),
                max_depth=model_config.get("max_depth", 3),
                # Low learning rate makes each tree a small correction instead of a large jump.
                learning_rate=model_config.get("learning_rate", 0.05),
                # Row/column sampling adds randomness and reduces dependence on one period or one feature.
                subsample=model_config.get("subsample", 0.8),
                colsample_bytree=model_config.get("colsample_bytree", 0.8),
                # logloss evaluates probability quality, not just hard up/down accuracy.
                eval_metric="logloss",
                tree_method="hist",
                # Fixed seed makes experiments reproducible.
                random_state=42,
            )
        except Exception:
            pass

    # Fallback keeps the engineering pipeline runnable if xgboost is unavailable on a machine.
    return RandomForestClassifier(
        n_estimators=200,
        max_depth=6,
        min_samples_leaf=20,
        random_state=42,
        n_jobs=-1,
    )


def fit_final_model(features: pd.DataFrame, model_config: dict, feature_columns: list[str]):
    """用全部已有训练样本拟合一个最终模型，用于后续模拟盘/应用加载。

    walk_forward_predict 的模型只在每个历史窗口里临时训练，用来评估“过去如果这么做会怎样”。
    那些临时模型不会被保存，因为它们只服务于回测。

    fit_final_model 的作用不同：
        1. 回测完成后，确认策略值得继续观察。
        2. 用当前所有已有标注样本重新训练一个最终模型。
        3. 保存到该策略自己的 models/<strategy_id>/latest_model.joblib。
        4. 后续 paper trading / 模拟盘可以加载这个模型，对新数据生成 prob_up。

    注意：
        保存模型不代表可以实盘。它只是把研究阶段模型变成可加载的工程产物。
    """
    model = make_classifier(model_config)
    model.fit(features[feature_columns], features["target_up"])
    return model


def walk_forward_predict(
    features: pd.DataFrame,
    config: WalkForwardConfig,
    model_config: dict,
    feature_columns: list[str],
) -> tuple[pd.DataFrame, list[dict]]:
    """Train on past windows and predict future windows.

    Example with train_window=3 years and test_window=1 quarter:
    2018-2020 train -> 2021 Q1 predict
    2018 Q2-2021 Q1 train -> 2021 Q2 predict

    Concatenating all predicted test windows gives a history of out-of-sample
    predictions, which is the input to the backtest.
    """
    frame = features.sort_values("date").reset_index(drop=True)
    unique_dates = pd.Series(frame["date"].sort_values().unique())
    predictions: list[pd.DataFrame] = []
    fold_metrics: list[dict] = []

    start_index = config.train_window_days
    while start_index < len(unique_dates):
        # Training window uses only dates strictly before the test window.
        train_start = unique_dates.iloc[max(0, start_index - config.train_window_days)]
        train_end = unique_dates.iloc[start_index - 1]
        test_end_index = min(start_index + config.test_window_days, len(unique_dates))
        test_start = unique_dates.iloc[start_index]
        test_end = unique_dates.iloc[test_end_index - 1]

        train = frame[(frame["date"] >= train_start) & (frame["date"] <= train_end)]
        test = frame[(frame["date"] >= test_start) & (frame["date"] <= test_end)]
        if len(train) < config.min_train_rows or test.empty:
            start_index = test_end_index
            continue

        model = make_classifier(model_config)
        model.fit(train[feature_columns], train["target_up"])

        # prob_up is P(target_up=1), i.e. model-estimated probability of next-period up move.
        prob_up = model.predict_proba(test[feature_columns])[:, 1]
        fold_pred = test[["date", "symbol", "close", "future_ret", "target_up"]].copy()
        fold_pred["prob_up"] = prob_up
        fold_pred["fold_train_start"] = train_start
        fold_pred["fold_train_end"] = train_end
        predictions.append(fold_pred)

        fold_metrics.append(_classification_metrics(test["target_up"], prob_up, test_start, test_end, len(train), len(test)))
        start_index = test_end_index

    if not predictions:
        raise ValueError("No walk-forward predictions produced. Check dates and min_train_rows.")
    return pd.concat(predictions, ignore_index=True), fold_metrics


def _classification_metrics(y_true: pd.Series, prob_up, test_start, test_end, train_rows: int, test_rows: int) -> dict:
    # 0.5 is used only to report classification accuracy. Trading uses probability_threshold in config.
    pred = (prob_up >= 0.5).astype(int)
    metrics = {
        "test_start": str(pd.Timestamp(test_start).date()),
        "test_end": str(pd.Timestamp(test_end).date()),
        "train_rows": train_rows,
        "test_rows": test_rows,
        "accuracy": float(accuracy_score(y_true, pred)),
    }
    if y_true.nunique() > 1:
        metrics["auc"] = float(roc_auc_score(y_true, prob_up))
        metrics["log_loss"] = float(log_loss(y_true, prob_up))
    else:
        metrics["auc"] = None
        metrics["log_loss"] = None
    return metrics
