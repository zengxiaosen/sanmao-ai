"""测试 DoubleEnsemble 集成分类器"""
import numpy as np
import pandas as pd
import pytest

from quant_llm.ensemble import EnsembleClassifier, make_ensemble_classifier


def test_ensemble_basic():
    """测试基本训练和预测"""
    # 生成模拟数据
    np.random.seed(42)
    X = pd.DataFrame(np.random.randn(100, 10))
    y = pd.Series(np.random.randint(0, 2, 100))
    
    # 训练集成模型
    ensemble = EnsembleClassifier(n_models=3, feature_fraction=0.8)
    ensemble.fit(X, y)
    
    # 检查模型数量
    assert len(ensemble.models) == 3
    assert len(ensemble.feature_masks) == 3
    
    # 预测
    X_test = pd.DataFrame(np.random.randn(20, 10))
    proba = ensemble.predict_proba(X_test)
    
    # 检查输出形状和值域
    assert proba.shape == (20, 2)
    assert np.all((proba >= 0) & (proba <= 1))
    assert np.allclose(proba.sum(axis=1), 1.0)


def test_ensemble_uncertainty():
    """测试不确定性估计"""
    np.random.seed(42)
    X = pd.DataFrame(np.random.randn(100, 10))
    y = pd.Series(np.random.randint(0, 2, 100))
    
    ensemble = EnsembleClassifier(n_models=5)
    ensemble.fit(X, y)
    
    X_test = pd.DataFrame(np.random.randn(20, 10))
    predictions, uncertainty = ensemble.predict_with_uncertainty(X_test)
    
    # 检查输出
    assert predictions.shape == (20,)
    assert uncertainty.shape == (20,)
    assert np.all((predictions >= 0) & (predictions <= 1))
    assert np.all(uncertainty >= 0)  # 标准差非负


def test_make_ensemble_classifier():
    """测试工厂函数"""
    config = {
        "n_models": 3,
        "feature_fraction": 0.7,
        "n_estimators": 100,
        "learning_rate": 0.1,
    }
    
    ensemble = make_ensemble_classifier(config)
    assert ensemble.n_models == 3
    assert ensemble.feature_fraction == 0.7
    
    # 训练验证
    np.random.seed(42)
    X = pd.DataFrame(np.random.randn(50, 8))
    y = pd.Series(np.random.randint(0, 2, 50))
    ensemble.fit(X, y)
    
    assert len(ensemble.models) == 3
