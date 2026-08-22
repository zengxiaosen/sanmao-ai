/*
Copyright (C) 2025 QuantumNous

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as
published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.

For commercial licensing, please contact support@quantumnous.com
*/

// 各厂商官方零售价（美元 / 1M tokens），用于模型广场「实付 ‖ 官方」对比。
// 数据抓自上游 model-plaza「官方价格」列，属外部厂商零售价、非本站计费逻辑。
// 新增在售模型时，请同步补充此表（缺项会在广场显示为“—”，不影响计费）。
export const OFFICIAL_PRICES = {
  'claude-fable-5': { input: 10, output: 50, cacheWrite: 12.5, cacheRead: 1 },
  'claude-haiku-4-5-20251001': { input: 1, output: 5, cacheWrite: 1.25, cacheRead: 0.1 },
  'claude-opus-4-5-20251101': { input: 5, output: 25, cacheWrite: 6.25, cacheRead: 0.5 },
  'claude-opus-4-6': { input: 5, output: 25, cacheWrite: 6.25, cacheRead: 0.5 },
  'claude-opus-4-7': { input: 5, output: 25, cacheWrite: 6.25, cacheRead: 0.5 },
  'claude-opus-4-8': { input: 5, output: 25, cacheWrite: 6.25, cacheRead: 0.5 },
  'claude-opus-5': { input: 5, output: 25, cacheWrite: 6.25, cacheRead: 0.5 },
  'claude-sonnet-4-5-20250929': { input: 3, output: 15, cacheWrite: 3.75, cacheRead: 0.3 },
  'claude-sonnet-4-6': { input: 3, output: 15, cacheWrite: 3.75, cacheRead: 0.3 },
  'claude-sonnet-5': { input: 2, output: 10, cacheWrite: 2.5, cacheRead: 0.2 },
  'codex-auto-review': { input: 0.2, output: 1.2, cacheWrite: 0.25, cacheRead: 0.02 },
  'gpt-5.2': { input: 1.75, output: 14, cacheWrite: null, cacheRead: 0.175 },
  'gpt-5.3-codex': { input: 1.75, output: 14, cacheWrite: null, cacheRead: 0.175 },
  'gpt-5.3-codex-spark': { input: 1.75, output: 14, cacheWrite: null, cacheRead: 0.175 },
  'gpt-5.4': { input: 2.5, output: 15, cacheWrite: null, cacheRead: 0.25 },
  'gpt-5.4-mini': { input: 0.75, output: 4.5, cacheWrite: null, cacheRead: 0.075 },
  'gpt-5.5': { input: 5, output: 30, cacheWrite: null, cacheRead: 0.5 },
  'gpt-5.6': { input: 5, output: 30, cacheWrite: 6.25, cacheRead: 0.5 },
  'gpt-5.6-luna': { input: 0.2, output: 1.2, cacheWrite: 0.25, cacheRead: 0.02 },
  'gpt-5.6-sol': { input: 5, output: 30, cacheWrite: 6.25, cacheRead: 0.5 },
  'gpt-5.6-terra': { input: 2, output: 12, cacheWrite: 2.5, cacheRead: 0.2 },
  'gpt-image-1': { input: 5, output: null, cacheWrite: null, cacheRead: 1.25 },
  'gpt-image-1.5': { input: 5, output: 10, cacheWrite: null, cacheRead: 1.25 },
  'gpt-image-2': { input: 5, output: 10, cacheWrite: null, cacheRead: 1.25 },
  'grok-4.6': { input: 2, output: 6, cacheWrite: null, cacheRead: 0.5 },
};

// 在售分组的展示顺序（Claude 三池在前，kiro 最划算打头；再 GPT 两池；最后 Grok）。
export const GROUP_ORDER = [
  'claude-kiro',
  'claude-max',
  'claude-distill',
  'gpt-pro',
  'gpt-cheap',
  'grok',
];

// 分组展示元数据：中文名、一句人话说明、图标 key、主色。
// 倍率不写死在这里，运行时从后端 group_ratio 读取，保证与计费一致。
export const GROUP_META = {
  'claude-kiro': {
    label: 'Claude · Kiro 企业版',
    desc: '可跑 Opus 4.8、1M 上下文，价格最低，日常首选。',
    icon: 'Claude',
    accent: 'orange',
    badge: '最划算',
  },
  'claude-max': {
    label: 'Claude · Max 巨稳定',
    desc: '可外接小龙虾 / Hermes / Claude Code，稳定性优先（稳定溢价）。',
    icon: 'Claude',
    accent: 'amber',
  },
  'claude-distill': {
    label: 'Claude · Max 可蒸馏',
    desc: '支持蒸馏玩法，稳定性最高（稳定溢价最高）。',
    icon: 'Claude',
    accent: 'red',
  },
  'gpt-pro': {
    label: 'GPT · PRO 稳定版',
    desc: '覆盖 GPT-5.6 全家 + Codex + 生图，稳定优先。',
    icon: 'OpenAI',
    accent: 'green',
  },
  'gpt-cheap': {
    label: 'GPT · PRO 特惠版',
    desc: '价格更低、偶发波动的性价比之选（不含 5.6 旗舰）。',
    icon: 'OpenAI',
    accent: 'teal',
    badge: '省钱',
  },
  grok: {
    label: 'Grok · 迭代版',
    desc: '主打 grok-4.6。',
    icon: 'Grok',
    accent: 'blue',
  },
};

export default OFFICIAL_PRICES;
