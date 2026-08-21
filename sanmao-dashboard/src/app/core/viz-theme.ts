// viz-theme.ts —— 看板统一视觉参数（dataviz 方法论的参数实例）。
// 所有页面从这里取颜色，禁止在页面里手写 hex。
// 调色板经 validate_palette.js 六项检查（含色盲模拟）通过。

// 分类色（固定顺序，永不循环生成新色）。斜杠后为校验值来源 palette.md。
export const CAT = {
  blue:    '#2a78d6',  // slot 1
  orange:  '#eb6834',  // slot 2
  aqua:    '#1baf7a',  // slot 3
  yellow:  '#eda100',  // slot 4
  magenta: '#e87ba4',  // slot 5
  green:   '#008300',  // slot 6
};
export const CAT_ORDER = [CAT.blue, CAT.orange, CAT.aqua, CAT.yellow, CAT.magenta, CAT.green];

// 顺序色（单蓝色系，浅→深 = 少→多）
export const SEQ_BLUE = ['#cde2fb', '#9ec5f4', '#6da7ec', '#3987e5', '#256abf', '#184f95', '#0d366b'];

// 发散色（蓝 ↔ 灰 ↔ 红：负 ↔ 零 ↔ 正）。中点必须是中性灰。
export const DIV = { neg: '#2a78d6', mid: '#f0efec', pos: '#e34948' };

// 状态色（语义保留：只用于好/坏/警示，绝不当系列色用）
export const STATUS = { good: '#0ca30c', warning: '#fab219', serious: '#ec835a', critical: '#d03b3b' };

// 强调模式：主角一个颜色，配角全灰
export const EMPHASIS = { hero: CAT.blue, context: '#c8c7c2' };

// 文字/表面
export const INK = { primary: '#0b0b0b', secondary: '#52514e', muted: '#8b8a85', surface: '#fcfcfb', grid: '#eceae6' };

// echarts 公共片段
export const AXIS_LABEL = { fontSize: 11, color: INK.secondary };
export const GRID_LINE = { lineStyle: { color: INK.grid } };

/** regime -> 颜色/名称（状态语义，非系列） */
export const REGIME_META: Record<string, { color: string; short: string; plain: string }> = {
  'bull 上行':      { color: STATUS.good,     short: '上行',   plain: '牛市：过去约3个月涨超8%' },
  'bear 下行':      { color: STATUS.critical, short: '下行',   plain: '熊市：过去约3个月跌超8%' },
  'high_vol 高波动': { color: STATUS.serious,  short: '高波动', plain: '恐慌期：VIX 超过 25' },
  'sideways 震荡':  { color: '#a8a7a2',       short: '震荡',   plain: '既没大涨大跌也不恐慌' },
};
