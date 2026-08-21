// 这些是后端 FastAPI 返回数据的「形状说明书」（TypeScript 类型）。
// 写页面代码时，编辑器靠它自动提示字段名、防止拼错。

// GET /health
export interface Health {
  status: string;
  strategy_id: string;
  symbols: string[];
  config: string;
  has_metrics: boolean;
  has_predictions: boolean;
}

// GET /factors —— 因子库热力图数据
export interface FactorRow {
  factor: string;      // 因子名，如 ret_5d
  group: string;       // 所属大类：量价 / 舆情 / 宏观
  values: number[];    // 最近若干天的 z-score 归一值（画热力图）
  latest: number;      // 最新一天的原始值
}
export interface FactorsResponse {
  factors: string[];
  dates: string[];
  matrix: FactorRow[];
  groups: Record<string, string[]>;
}

// GET /signals —— 信号页
export interface SignalRow {
  date: string;
  close: number;
  prob_up: number;         // 模型预测的上涨概率
  position?: number;       // 仓位：1=持有 0=空仓
  future_ret?: number;
}
export interface SignalsResponse {
  rows: SignalRow[];
  latest: SignalRow;
  action: string;          // 今日建议：long 持有 / flat 空仓
}

// GET /backtest —— 绩效页
export interface BacktestDaily {
  date: string;
  equity: number;          // 资金曲线（从 1.0 开始）
  drawdown: number;        // 回撤
  strategy_ret: number;
}
export interface BacktestSummary {
  total_return: number;
  annual_return: number;
  sharpe: number;
  max_drawdown: number;
  mean_daily_turnover: number;
  hit_rate_when_in_market: number;
  exposure: number;
}
export interface BacktestResponse {
  daily: BacktestDaily[];
  summary: BacktestSummary;
  fold_metrics: any[];
  feature_columns: string[];
}

// GET /factor-analytics —— 因子体检页（P3）
export interface ImportancePoint {
  window_end: string;      // 训练窗口截止日
  factor: string;
  importance: number;      // 该窗口模型里此因子的重要性占比（和为 1）
}
export interface DecayRow {
  factor: string;
  status: 'active' | 'decaying' | 'failed' | 'sparse';
  recent_importance: number;
  importance_trend: number;   // 负=重要性在下降
  recent_abs_t: number;       // 最近 |t| 均值，越大越显著
  coverage?: number;          // 非零天数占比；sparse 判定依据
}
export interface ReplacementRow {
  failed_factor: string;
  group: string;
  replacement: string | null;
  replacement_importance: number | null;
}
export interface AttributionRow {
  date: string;
  factor: string;
  contribution: number;
}
export interface FactorAnalyticsResponse {
  importance_timeline: ImportancePoint[];
  decay: DecayRow[];
  replacements: ReplacementRow[];
  attribution: AttributionRow[];
}

// GET /regime —— 市场状态（P4）
export interface RegimeDay {
  date: string;
  ret_trend: number;       // 趋势观察窗口收益
  vol_20d: number;
  vix_level: number | null;
  regime: string;          // bull 上行 / bear 下行 / high_vol 高波动 / sideways 震荡
}
export interface RegimeFactorPerf {
  regime: string;
  factor: string;
  mean_beta: number;
  mean_abs_t: number;
  days: number;
}
export interface RegimeResponse {
  timeline: RegimeDay[];
  factor_performance: RegimeFactorPerf[];
}

// GET /review —— 自动复盘（P4），对应 review.json
export interface ReviewResponse {
  generated_at?: string;
  data_range?: { start?: string; end?: string };
  backtest?: Partial<BacktestSummary>;
  regime?: { latest: string; latest_date: string; recent_distribution: Record<string, number> };
  top_factors?: { factor: string; importance: number }[];
  factor_health?: { active: number; decaying: number; failed: number; sparse?: number; unhealthy_factors: string[] };
  replacements?: { failed_factor: string; replacement: string; group: string }[];
  latest_signal?: { date: string; symbol?: string; close?: number; prob_up?: number; action?: string };
  narrative?: string[];
}
