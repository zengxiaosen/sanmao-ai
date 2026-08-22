"""多股票选股器

核心逻辑：
1. 为每只股票独立训练模型
2. 每日预测所有股票的上涨概率
3. 选择 top-K 构建投资组合
4. 支持 ensemble 降低过拟合
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from quant_llm.modeling import WalkForwardConfig, make_classifier, walk_forward_predict


@dataclass
class MultiStockConfig:
    """多股票选股配置"""
    symbols: list[str]  # 股票池
    top_k: int = 3  # 选择 top-K 支股票
    use_ensemble: bool = True  # 是否使用集成模型
    equal_weight: bool = True  # 是否等权配置（False=按概率加权）


class MultiStockSelector:
    """多股票选股器"""
    
    def __init__(self, config: MultiStockConfig):
        self.config = config
        self.models = {}  # {symbol: trained_model}
        
    def train_all(
        self,
        features_dict: dict[str, pd.DataFrame],
        model_config: dict,
        feature_columns: list[str],
    ) -> None:
        """为每只股票训练独立模型
        
        Args:
            features_dict: {symbol: features_df}，每个 df 包含 target_up 列
            model_config: LightGBM 配置
            feature_columns: 特征列名列表
        """
        for symbol in self.config.symbols:
            if symbol not in features_dict:
                print(f"Warning: No data for {symbol}, skipping")
                continue
                
            features = features_dict[symbol]
            print(f"Training model for {symbol}: {len(features)} samples")
            
            # 训练模型
            model = make_classifier(model_config, use_ensemble=self.config.use_ensemble)
            X = features[feature_columns]
            y = features["target_up"]
            model.fit(X, y)
            
            self.models[symbol] = model
            
    def predict_all(
        self,
        features_dict: dict[str, pd.DataFrame],
        feature_columns: list[str],
        date: str | None = None,
    ) -> pd.DataFrame:
        """预测所有股票的上涨概率
        
        Args:
            features_dict: {symbol: features_df}
            feature_columns: 特征列名
            date: 指定日期（用于回测），None=使用最新一行
            
        Returns:
            DataFrame with columns: [symbol, prob_up, uncertainty]
        """
        results = []
        
        for symbol, model in self.models.items():
            if symbol not in features_dict:
                continue
                
            features = features_dict[symbol]
            
            # 获取目标日期的特征
            if date:
                features = features[features["date"] == date]
            else:
                features = features.tail(1)
            
            if features.empty:
                continue
            
            X = features[feature_columns]
            
            # 预测
            if hasattr(model, "predict_with_uncertainty"):
                # Ensemble 模型返回不确定性
                prob, uncertainty = model.predict_with_uncertainty(X)
                prob = prob[0]
                uncertainty = uncertainty[0]
            else:
                # 单模型
                prob = model.predict_proba(X)[0, 1]
                uncertainty = 0.0
            
            results.append({
                "symbol": symbol,
                "prob_up": prob,
                "uncertainty": uncertainty,
            })
        
        return pd.DataFrame(results).sort_values("prob_up", ascending=False)
    
    def select_portfolio(
        self,
        predictions: pd.DataFrame,
        max_uncertainty: float = 0.2,
    ) -> pd.DataFrame:
        """根据预测结果选择投资组合
        
        Args:
            predictions: predict_all 的输出
            max_uncertainty: 不确定性阈值（超过此值的股票被过滤）
            
        Returns:
            DataFrame with columns: [symbol, prob_up, weight]
        """
        # 过滤高不确定性的股票
        valid = predictions[predictions["uncertainty"] <= max_uncertainty].copy()
        
        if len(valid) == 0:
            print("Warning: All stocks filtered by uncertainty, using top prediction anyway")
            valid = predictions.head(1).copy()
        
        # 选择 top-K
        selected = valid.head(self.config.top_k).copy()
        
        # 分配权重
        if self.config.equal_weight:
            selected["weight"] = 1.0 / len(selected)
        else:
            # 按概率加权
            probs = selected["prob_up"].values
            weights = probs / probs.sum()
            selected["weight"] = weights
        
        return selected[["symbol", "prob_up", "weight"]]


def backtest_multi_stock(
    features_dict: dict[str, pd.DataFrame],
    config: MultiStockConfig,
    model_config: dict,
    feature_columns: list[str],
    train_end_date: str,
) -> pd.DataFrame:
    """多股票组合回测
    
    Args:
        features_dict: {symbol: features_df}
        config: 选股配置
        model_config: 模型配置
        feature_columns: 特征列
        train_end_date: 训练截止日期（之后的数据用于回测）
        
    Returns:
        回测结果 DataFrame: [date, selected_symbols, portfolio_return]
    """
    selector = MultiStockSelector(config)
    
    # 1. 训练阶段：用 train_end_date 之前的数据训练
    train_features = {}
    for symbol, df in features_dict.items():
        train_features[symbol] = df[df["date"] <= train_end_date]
    
    print(f"Training models up to {train_end_date}...")
    selector.train_all(train_features, model_config, feature_columns)
    
    # 2. 回测阶段：在 train_end_date 之后的日期上滚动预测
    test_dates = []
    for df in features_dict.values():
        test_dates.extend(df[df["date"] > train_end_date]["date"].unique())
    test_dates = sorted(set(test_dates))
    
    backtest_results = []
    
    for date in test_dates:
        # 预测当日各股票概率
        predictions = selector.predict_all(features_dict, feature_columns, date=date)
        
        if predictions.empty:
            continue
        
        # 选择组合
        portfolio = selector.select_portfolio(predictions)
        
        # 计算组合收益（简化：假设持有 1 天）
        daily_returns = []
        for _, row in portfolio.iterrows():
            symbol = row["symbol"]
            weight = row["weight"]
            
            # 获取该股票次日的实际收益
            stock_data = features_dict[symbol]
            today_idx = stock_data[stock_data["date"] == date].index
            if len(today_idx) == 0 or today_idx[0] + 1 >= len(stock_data):
                continue
            
            next_row = stock_data.iloc[today_idx[0] + 1]
            stock_return = next_row.get("daily_return", 0.0)
            daily_returns.append(weight * stock_return)
        
        portfolio_return = sum(daily_returns) if daily_returns else 0.0
        
        backtest_results.append({
            "date": date,
            "selected_symbols": ",".join(portfolio["symbol"].tolist()),
            "portfolio_return": portfolio_return,
        })
    
    return pd.DataFrame(backtest_results)
