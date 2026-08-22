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

import React from 'react';
import { Card, Skeleton } from '@douyinfe/semi-ui';
import { renderNumber, renderQuota } from '../../helpers';

// 净赚系数：所有分组定价 = 上游成本 ×1.3，故净赚 = 进账 × 0.3 / 1.3
const NET_PROFIT_FACTOR = 0.3 / 1.3;

const safeRenderQuota = (quota, digits = 2) => {
  const formatted = renderQuota(Number(quota || 0), digits);
  if (String(formatted).includes('NaN')) {
    return `${renderNumber(Number(quota || 0))}`;
  }
  return formatted;
};

const BigNumber = ({ label, value, accent, loading }) => (
  <div
    className='rounded-2xl p-5'
    style={{
      border: '1px solid var(--semi-color-border)',
      background: 'var(--semi-color-bg-0)',
      boxShadow: '0 8px 24px var(--semi-color-shadow)',
    }}
  >
    <div
      className='mb-2 text-sm font-medium'
      style={{ color: 'var(--semi-color-text-2)' }}
    >
      {label}
    </div>
    <Skeleton
      loading={loading}
      active
      placeholder={<Skeleton.Title style={{ width: 120, height: 40 }} />}
    >
      <div
        className='text-3xl font-bold leading-tight sm:text-4xl'
        style={{ color: accent || 'var(--semi-color-text-0)' }}
      >
        {value}
      </div>
    </Skeleton>
  </div>
);

const BusinessSummaryPanel = ({
  loading,
  todayQuota,
  monthQuota,
  monthCount,
  totalBalance,
  t,
}) => {
  const netProfit = Number(monthQuota || 0) * NET_PROFIT_FACTOR;

  return (
    <Card
      className='mb-4 overflow-hidden !rounded-2xl border-0 shadow-sm'
      style={{
        background:
          'linear-gradient(135deg, var(--semi-color-primary-light-default), var(--semi-color-bg-1) 45%, var(--semi-color-bg-0))',
        border: '1px solid var(--semi-color-border)',
      }}
      bodyStyle={{ padding: 20 }}
    >
      <h2
        className='mb-4 text-lg font-semibold'
        style={{ color: 'var(--semi-color-text-0)' }}
      >
        {t('老板，今天的账')}
      </h2>

      <div className='grid grid-cols-2 gap-4 lg:grid-cols-4'>
        <BigNumber
          loading={loading}
          label={t('今天进账')}
          value={safeRenderQuota(todayQuota)}
          accent='#10b981'
        />
        <BigNumber
          loading={loading}
          label={t('本月进账')}
          value={safeRenderQuota(monthQuota)}
          accent='#10b981'
        />
        <BigNumber
          loading={loading}
          label={t('账户余额（用户还没花的钱）')}
          value={safeRenderQuota(totalBalance)}
        />
        <BigNumber
          loading={loading}
          label={t('本月调用次数')}
          value={Number(monthCount || 0).toLocaleString()}
        />
      </div>

      <div
        className='mt-4 text-sm'
        style={{ color: 'var(--semi-color-text-1)' }}
      >
        {t('本月约净赚')} {safeRenderQuota(netProfit)}
      </div>
    </Card>
  );
};

export default BusinessSummaryPanel;
