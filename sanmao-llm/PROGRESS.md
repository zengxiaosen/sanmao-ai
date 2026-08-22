# 量化系统升级进度

## ✅ 已完成（2024-08-21）

### 1. LightGBM 替换 XGBoost
- [x] 安装 LightGBM 4.7.0
- [x] 修改 modeling.py：XGBClassifier → LGBMClassifier
- [x] 参数适配：num_leaves, subsample_freq, reg_alpha/lambda
- [x] 测试验证：模型正常加载

**文件变更**：
- `src/quant_llm/modeling.py`：替换分类器，优化超参

### 2. DoubleEnsemble 风控层
- [x] 创建 `src/quant_llm/ensemble.py`
- [x] 实现 EnsembleClassifier（5 模型集成 + 不确定性估计）
- [x] 集成到 modeling.py（use_ensemble 参数）
- [x] 编写单元测试（3/3 passed）

**核心功能**：
- 训练 N 个 LightGBM（不同随机种子 + 特征采样）
- 预测时取中位数（降低过拟合）
- 输出不确定性（标准差）用于风控

**文件变更**：
- `src/quant_llm/ensemble.py`（新增）
- `src/quant_llm/modeling.py`（集成 ensemble 支持）
- `tests/test_ensemble.py`（新增）

### 3. 多股票选股框架
- [x] 创建 `src/quant_llm/multi_stock_selector.py`
- [x] MultiStockSelector 类（独立训练、组合预测）
- [x] backtest_multi_stock 函数（组合回测）

**核心功能**：
- 为每只股票独立训练模型
- 每日预测所有股票上涨概率
- 按概率排序，选 top-K 构建组合
- 支持等权/概率加权配置
- 不确定性过滤（>0.2 剔除）

**文件变更**：
- `src/quant_llm/multi_stock_selector.py`（新增）

### 4. 前端回撤修复
- [x] 修正回撤曲线显示（负数 → 正数）
- [x] y 轴反向（0 在顶部，向下表示损失）
- [x] 更新 explain 文案（正确的回撤公式）

**文件变更**：
- `sanmao-dashboard/src/app/pages/performance/performance.component.ts`

---

## 🚧 进行中

### 数据源扩展（遇到问题）
- ❌ yfinance：服务器网络超时（被墙）
- ❌ AKShare：API 接口变更（stock_us_hist 不可用）

**临时方案**：
- 先用现有 NVDA 数据验证架构
- 后续考虑：
  1. 本地下载 → 上传到服务器
  2. 使用付费数据源（Polygon.io）
  3. 扩展到 A 股（Tushare Pro）

---

## 📋 待办事项

### 第一阶段剩余任务
- [ ] **回测验证**：单票 NVDA 用 LightGBM + Ensemble，对比 XGBoost 性能
- [ ] **性能基准**：记录年化收益、夏普比率、最大回撤
- [ ] **解决数据源**：找到稳定的美股/A股数据获取方式
- [ ] **6 支科技股回测**：用模拟数据先跑通多股票选股流程

### 第二阶段：Claude 风控（预计 1 周）
- [ ] 公告爬虫（SEC EDGAR / 巨潮资讯）
- [ ] Claude API 集成（风险评级 prompt）
- [ ] 成本控制（只读标题 + 前 500 字）
- [ ] 集成到选股管线

### 第三阶段：PPO 调仓（预计 2 周）
- [ ] 安装 FinRL + Stable-Baselines3
- [ ] 定义状态空间、动作空间、奖励函数
- [ ] 训练 PPO agent（2021-2024 数据）
- [ ] 回测对比：RL 调仓 vs 等权配置

### 第四阶段：跨资产配置（预计 1 个月）
- [ ] 扩展到黄金、原油、美债 ETF
- [ ] A 股行业轮动（新能源、半导体、消费）
- [ ] 宏观因子驱动策略

---

## 📊 性能基准（待测试）

| 指标 | XGBoost 单票 | LightGBM 单票 | LightGBM Ensemble | 多股票组合 |
|------|-------------|--------------|------------------|-----------|
| 年化收益 | 60% | ? | ? | ? |
| 夏普比率 | 1.2 | ? | ? | ? |
| 最大回撤 | 52.9% | ? | ? | ? |
| 训练时间 | - | ? | ? | ? |

---

## 🛠️ 技术栈

| 模块 | 技术选型 | 状态 |
|------|---------|------|
| 树模型 | LightGBM 4.7.0 | ✅ |
| 集成学习 | EnsembleClassifier（自研） | ✅ |
| 数据源 | 待定（yfinance/AKShare 不可用） | ⚠️ |
| 回测框架 | 自研（基于 pandas） | ✅ |
| 强化学习 | FinRL + Stable-Baselines3 | 🔜 |
| LLM 风控 | Claude 3.5 Sonnet | 🔜 |

---

## 📝 备注

1. **数据源问题**是当前最大阻塞点，需要优先解决
2. LightGBM + Ensemble 架构已搭建完成，等数据验证
3. 多股票选股框架代码完成，需要实际数据测试
4. 前端回撤修复已上线：http://120.24.144.153/quant/performance

---

**最后更新**：2024-08-21 21:15  
**下一步**：解决数据源问题，运行完整回测验证
