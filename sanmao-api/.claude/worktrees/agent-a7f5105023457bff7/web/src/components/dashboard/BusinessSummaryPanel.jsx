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

import React, { useMemo } from 'react';
import { Card, Skeleton, Tag } from '@douyinfe/semi-ui';
import {
  ArrowRight,
  Banknote,
  CircleDollarSign,
  Coins,
  Database,
  MinusCircle,
  ReceiptText,
  TrendingUp,
} from 'lucide-react';
import { renderNumber, renderQuota } from '../../helpers';

const safeRenderQuota = (quota, digits = 2) => {
  const formatted = renderQuota(quota, digits);
  if (String(formatted).includes('NaN')) {
    return `${renderNumber(Number(quota || 0))} quota`;
  }
  return formatted;
};

const MetricBlock = ({ icon, label, value, hint, loading }) => (
  <div
    className='rounded-xl p-4 shadow-sm'
    style={{
      border: '1px solid var(--semi-color-border)',
      background: 'var(--semi-color-bg-0)',
      boxShadow: '0 10px 28px var(--semi-color-shadow)',
    }}
  >
    <div
      className='mb-3 flex items-center gap-2 text-xs font-medium'
      style={{ color: 'var(--semi-color-text-2)' }}
    >
      <span
        className='flex h-7 w-7 items-center justify-center rounded-lg'
        style={{
          background: 'var(--semi-color-primary)',
          color: 'var(--semi-color-white)',
        }}
      >
        {icon}
      </span>
      {label}
    </div>
    <Skeleton
      loading={loading}
      active
      placeholder={<Skeleton.Title style={{ width: 96, height: 28 }} />}
    >
      <div
        className='text-2xl font-semibold'
        style={{ color: 'var(--semi-color-text-0)' }}
      >
        {value}
      </div>
    </Skeleton>
    <div
      className='mt-2 min-h-[36px] text-xs leading-5'
      style={{ color: 'var(--semi-color-text-2)' }}
    >
      {hint}
    </div>
  </div>
);

const BusinessSummaryPanel = ({
  loading,
  consumeQuota,
  consumeTokens,
  times,
  upstreamCostQuota,
  usageCostQuota,
  fixedCostQuota,
  netProfitQuota,
  profitRate,
  costConfigured,
  costConfiguredLogs,
  costUnconfiguredLogs,
  t,
}) => {
  const summary = useMemo(() => {
    const requestCount = Number(times || 0);
    const tokenCount = Number(consumeTokens || 0);
    const grossRevenue = Number(consumeQuota || 0);
    const upstreamCostConfigured = Boolean(costConfigured);
    const upstreamCost = Number(upstreamCostQuota || 0);
    const usageCost = Number(usageCostQuota || 0);
    const fixedCost = Number(fixedCostQuota || 0);
    const netProfit = upstreamCostConfigured
      ? Number(netProfitQuota || 0)
      : null;
    const effectiveProfitRate = upstreamCostConfigured
      ? Number(profitRate || 0)
      : null;
    const quotaPerMillionTokens =
      tokenCount > 0 ? (grossRevenue / tokenCount) * 1000000 : 0;

    return {
      requestCount,
      tokenCount,
      grossRevenue,
      upstreamCostConfigured,
      upstreamCost,
      usageCost,
      fixedCost,
      netProfit,
      profitRate: effectiveProfitRate,
      costConfiguredLogs: Number(costConfiguredLogs || 0),
      costUnconfiguredLogs: Number(costUnconfiguredLogs || 0),
      quotaPerMillionTokens,
    };
  }, [
    consumeQuota,
    consumeTokens,
    times,
    upstreamCostQuota,
    usageCostQuota,
    fixedCostQuota,
    netProfitQuota,
    profitRate,
    costConfigured,
    costConfiguredLogs,
    costUnconfiguredLogs,
  ]);

  return (
    <Card
      className='mb-4 overflow-hidden !rounded-2xl border-0 shadow-sm'
      style={{
        background:
          'linear-gradient(135deg, var(--semi-color-primary-light-default), var(--semi-color-bg-1) 45%, var(--semi-color-bg-0))',
        border: '1px solid var(--semi-color-border)',
      }}
      bodyStyle={{ padding: 0 }}
    >
      <div className='grid grid-cols-1 gap-0 lg:grid-cols-[1.15fr_1.85fr]'>
        <div
          className='p-5'
          style={{
            borderRight: '1px solid var(--semi-color-border)',
            color: 'var(--semi-color-text-0)',
          }}
        >
          <div
            className='mb-3 inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium'
            style={{
              background: 'var(--semi-color-primary-light-default)',
              color: 'var(--semi-color-primary)',
              border: '1px solid var(--semi-color-primary-light-active)',
            }}
          >
            <CircleDollarSign size={14} />
            {t('赚钱看板')}
          </div>
          <h2
            className='text-xl font-semibold'
            style={{ color: 'var(--semi-color-text-0)' }}
          >
            {t('先看用户付了多少，再填上游成本，最后才是你赚的差价')}
          </h2>
          <div
            className='mt-3 space-y-2 text-sm leading-6'
            style={{ color: 'var(--semi-color-text-1)' }}
          >
            <div className='flex gap-2'>
              <ArrowRight
                size={16}
                className='mt-1 flex-none'
                style={{ color: '#34d399' }}
              />
              <span>{t('毛收入：用户调用模型后，Sanmao 实际从用户账户扣掉的钱。')}</span>
            </div>
            <div className='flex gap-2'>
              <ArrowRight
                size={16}
                className='mt-1 flex-none'
                style={{ color: '#fbbf24' }}
              />
              <span>{t('上游成本：你采购 Aliyun、VisionCoder、Yaxi 等 API 实际花掉的钱。')}</span>
            </div>
            <div className='flex gap-2'>
              <ArrowRight
                size={16}
                className='mt-1 flex-none'
                style={{ color: '#fb7185' }}
              />
              <span>{t('净利润/差价：毛收入减去上游成本。当前还没有配置上游成本，所以不能算净利润。')}</span>
            </div>
          </div>
          <div className='mt-4 flex flex-wrap gap-2'>
            <Tag color='green' shape='circle'>
              {t('当前显示的是毛收入')}
            </Tag>
            <Tag color='orange' shape='circle'>
              {t('净利润等待成本配置')}
            </Tag>
          </div>
        </div>

        <div className='grid grid-cols-1 gap-3 p-4 sm:grid-cols-2 xl:grid-cols-3'>
          <MetricBlock
            loading={loading}
            icon={<ReceiptText size={16} />}
            label={t('毛收入：用户实际付的钱')}
            value={safeRenderQuota(summary.grossRevenue, 2)}
            hint={t('当前筛选时间内，用户账户被扣掉的金额。不是净利润。')}
          />
          <MetricBlock
            loading={loading}
            icon={<Banknote size={16} />}
            label={t('上游成本：你实际花的钱')}
            value={
              summary.upstreamCostConfigured
                ? safeRenderQuota(summary.upstreamCost, 2)
                : t('未配置')
            }
            hint={t('需要给每个渠道配置采购价后才能自动计算，例如 Aliyun、VisionCoder、Yaxi。')}
          />
          <MetricBlock
            loading={loading}
            icon={<TrendingUp size={16} />}
            label={t('净利润：你赚的差价')}
            value={
              summary.upstreamCostConfigured
                ? safeRenderQuota(summary.netProfit, 2)
                : t('暂不能算')
            }
            hint={t('净利润 = 毛收入 - 上游成本。当前不要把毛收入当成利润。')}
          />
          <MetricBlock
            loading={loading}
            icon={<MinusCircle size={16} />}
            label={t('毛利率')}
            value={
              summary.profitRate === null
                ? t('暂不能算')
                : `${(summary.profitRate * 100).toFixed(2)}%`
            }
            hint={t('毛利率 = 净利润 / 毛收入。缺少上游成本时不能计算。')}
          />
          <MetricBlock
            loading={loading}
            icon={<Coins size={16} />}
            label={t('按量上游成本')}
            value={
              summary.upstreamCostConfigured
                ? safeRenderQuota(summary.usageCost, 2)
                : t('未配置')
            }
            hint={t('VisionCoder 这类按积分/token 扣费的成本，会按实际输入输出 tokens 计算。')}
          />
          <MetricBlock
            loading={loading}
            icon={<Database size={16} />}
            label={t('固定成本折算')}
            value={
              summary.upstreamCostConfigured
                ? safeRenderQuota(summary.fixedCost, 2)
                : t('未配置')
            }
            hint={t('阿里云 Token Plan、包月套餐、服务器月租等，会按当前筛选时间折算。')}
          />
        </div>
        <div
          className='grid grid-cols-1 gap-3 px-4 pb-4 sm:grid-cols-2'
          style={{ color: 'var(--semi-color-text-2)' }}
        >
          <div className='text-xs leading-5'>
            {t('Tokens：本周期模型输入和输出合计消耗。')} {renderNumber(summary.tokenCount)}
          </div>
          <div className='text-xs leading-5'>
            {t('每 1M Tokens 毛收入：')}
            {safeRenderQuota(summary.quotaPerMillionTokens, 2)}
          </div>
        </div>
        {!summary.upstreamCostConfigured && summary.requestCount > 0 && (
          <div
            className='px-4 pb-4 text-xs leading-5'
            style={{ color: 'var(--semi-color-warning)' }}
          >
            {t('还有 ${count} 条调用日志没有匹配到上游成本配置，所以净利润暂不能算。')
              .replace('${count}', renderNumber(summary.costUnconfiguredLogs))}
          </div>
        )}
      </div>
    </Card>
  );
};

export default BusinessSummaryPanel;
