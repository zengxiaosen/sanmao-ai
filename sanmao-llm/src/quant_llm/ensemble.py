"""DoubleEnsemble: 多模型集成降低过拟合

核心思路：
1. 训练 N 个 LightGBM（不同随机种子 + 特征采样）
2. 预测时取中位数（比均值更鲁棒）
3. 计算预测标准差作为不确定性指标

用法：
    ensemble = EnsembleClassifier(n_models=5, feature_fraction=0.8)
    ensemble.fit(X_train, y_train)
    pred, uncertainty = ensemble.predict_with_uncertainty(X_test)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier


class EnsembleClassifier:
    """多个 LightGBM 组成的集成分类器"""

    def __init__(
        self,
        n_models: int = 5,
        feature_fraction: float = 0.8,
        base_config: dict | None = None,
    ):
        """
        Args:
            n_models: 集成模型数量
            feature_fraction: 每个模型随机采样的特征比例
            base_config: LightGBM 基础配置
        """
        self.n_models = n_models
        self.feature_fraction = feature_fraction
        self.base_config = base_config or {}
        self.models: list[LGBMClassifier] = []
        self.feature_masks: list[np.ndarray] = []

    def fit(self, X: pd.DataFrame | np.ndarray, y: pd.Series | np.ndarray) -> None:
        """训练多个模型，每个用不同的特征子集"""
        if isinstance(X, pd.DataFrame):
            X_arr = X.values
            feature_names = X.columns.tolist()
        else:
            X_arr = X
            feature_names = None

        n_features = X_arr.shape[1]
        n_sample_features = max(1, int(n_features * self.feature_fraction))

        for i in range(self.n_models):
            # 每个模型用不同的随机种子
            seed = 42 + i
            np.random.seed(seed)

            # 随机选择特征子集
            feature_indices = np.random.choice(n_features, n_sample_features, replace=False)
            self.feature_masks.append(feature_indices)

            # 训练模型
            config = {
                **self.base_config,
                "random_state": seed,
                "n_estimators": self.base_config.get("n_estimators", 200),
                "num_leaves": self.base_config.get("num_leaves", 31),
                "learning_rate": self.base_config.get("learning_rate", 0.05),
                "subsample": self.base_config.get("subsample", 0.8),
                "subsample_freq": 1,
                "colsample_bytree": self.base_config.get("colsample_bytree", 0.8),
                "min_child_samples": 20,
                "reg_alpha": 0.1,
                "reg_lambda": 0.1,
                "objective": "binary",
                "metric": "binary_logloss",
                "verbosity": -1,
            }

            model = LGBMClassifier(**config)
            X_subset = X_arr[:, feature_indices]
            model.fit(X_subset, y)
            self.models.append(model)

    def predict_proba(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        """预测概率（多模型中位数）"""
        if isinstance(X, pd.DataFrame):
            X_arr = X.values
        else:
            X_arr = X

        # 收集所有模型的预测
        all_preds = []
        for model, feature_indices in zip(self.models, self.feature_masks):
            X_subset = X_arr[:, feature_indices]
            pred = model.predict_proba(X_subset)[:, 1]  # 只要正类概率
            all_preds.append(pred)

        all_preds = np.array(all_preds)  # shape: (n_models, n_samples)

        # 返回中位数作为最终预测
        median_pred = np.median(all_preds, axis=0)
        return np.column_stack([1 - median_pred, median_pred])

    def predict_with_uncertainty(self, X: pd.DataFrame | np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """预测 + 不确定性

        Returns:
            predictions: 预测的正类概率（中位数）
            uncertainty: 预测的标准差（值越大 = 模型分歧越大 = 越不确定）
        """
        if isinstance(X, pd.DataFrame):
            X_arr = X.values
        else:
            X_arr = X

        all_preds = []
        for model, feature_indices in zip(self.models, self.feature_masks):
            X_subset = X_arr[:, feature_indices]
            pred = model.predict_proba(X_subset)[:, 1]
            all_preds.append(pred)

        all_preds = np.array(all_preds)
        predictions = np.median(all_preds, axis=0)
        uncertainty = np.std(all_preds, axis=0)

        return predictions, uncertainty


def make_ensemble_classifier(model_config: dict) -> EnsembleClassifier:
    """工厂函数：创建集成分类器

    Args:
        model_config: 配置字典，可包含 n_models, feature_fraction 等

    Returns:
        配置好的 EnsembleClassifier
    """
    n_models = model_config.get("n_models", 5)
    feature_fraction = model_config.get("feature_fraction", 0.8)

    return EnsembleClassifier(
        n_models=n_models,
        feature_fraction=feature_fraction,
        base_config=model_config,
    )
