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
import { Tag, Typography } from '@douyinfe/semi-ui';
import {
  renderModelTag,
  calculateModelPrice,
  getOfficialPrice,
  formatTokenPriceUSD,
} from '../../../../../helpers';

const { Text } = Typography;

// 一行价格：标签 + 数值（可选删除线 / 静音色）
const PriceLine = ({ label, value, muted = false, strike = false }) => {
  if (value === null || value === undefined || value === '') return null;
  return (
    <div className='flex items-baseline gap-1 leading-5'>
      <span
        style={{
          fontSize: 11,
          color: 'var(--semi-color-text-2)',
          width: 14,
          flexShrink: 0,
        }}
      >
        {label}
      </span>
      <span
        style={{
          fontSize: 13,
          color: muted ? 'var(--semi-color-text-2)' : 'var(--semi-color-text-0)',
          textDecoration: strike ? 'line-through' : 'none',
          fontWeight: strike ? 400 : 600,
        }}
      >
        {value}
      </span>
    </div>
  );
};

export const getGroupedPricingColumns = ({
  t,
  group,
  groupRatio,
  copyText,
  currency,
  siteDisplayType,
  tokenUnit,
  displayPrice,
}) => {
  const unitLabel = tokenUnit === 'K' ? 'K' : 'M';
  const isTokens = siteDisplayType === 'TOKENS';

  const priceCache = new WeakMap();
  const getPaid = (record) => {
    let c = priceCache.get(record);
    if (!c) {
      c = calculateModelPrice({
        record,
        selectedGroup: group,
        groupRatio,
        tokenUnit,
        displayPrice,
        currency,
        quotaDisplayType: siteDisplayType,
      });
      priceCache.set(record, c);
    }
    return c;
  };

  const fmtOfficial = (usdPer1M) =>
    formatTokenPriceUSD(usdPer1M, {
      displayPrice,
      currency,
      tokenUnit,
    });

  const modelNameColumn = {
    title: t('模型'),
    dataIndex: 'model_name',
    render: (text) =>
      renderModelTag(text, { onClick: () => copyText(text) }),
    onFilter: (value, record) =>
      record.model_name.toLowerCase().includes(value.toLowerCase()),
  };

  const paidColumn = {
    title: isTokens
      ? t('实付倍率')
      : t('实付价格') + ` · /1${unitLabel}`,
    dataIndex: 'paid',
    render: (_, record) => {
      const p = getPaid(record);
      if (record.quota_type === 1) {
        return (
          <PriceLine label={t('次')} value={p.price} />
        );
      }
      if (isTokens) {
        return (
          <div>
            <PriceLine label={t('入')} value={p.inputRatio != null ? `${p.inputRatio}x` : null} />
            <PriceLine label={t('出')} value={p.completionRatio != null ? `${p.completionRatio}x` : null} muted />
          </div>
        );
      }
      return (
        <div>
          <PriceLine label={t('入')} value={p.inputPrice} />
          <PriceLine label={t('出')} value={p.completionPrice} muted />
          {p.cachePrice && (
            <PriceLine label={t('存')} value={p.cachePrice} muted />
          )}
        </div>
      );
    },
  };

  const officialColumn = {
    title: t('官方价格') + ` · /1${unitLabel}`,
    dataIndex: 'official',
    render: (_, record) => {
      const off = getOfficialPrice(record.model_name);
      if (!off || isTokens) return <Text type='tertiary'>—</Text>;
      const oIn = fmtOfficial(off.input);
      const oOut = fmtOfficial(off.output);
      const oCache = fmtOfficial(off.cacheRead);
      return (
        <div>
          <PriceLine label={t('入')} value={oIn} muted strike />
          <PriceLine label={t('出')} value={oOut} muted strike />
          {oCache && <PriceLine label={t('存')} value={oCache} muted strike />}
        </div>
      );
    },
  };

  const discountColumn = {
    title: t('对比官方'),
    dataIndex: 'discount',
    align: 'center',
    render: (_, record) => {
      const off = getOfficialPrice(record.model_name);
      if (!off || !off.input || record.quota_type !== 0 || isTokens) {
        return <Text type='tertiary'>—</Text>;
      }
      const gr = groupRatio[group];
      if (gr === undefined || gr === null) return <Text type='tertiary'>—</Text>;
      const paidUSD = Number(record.model_ratio) * 2 * Number(gr);
      const ratio = paidUSD / Number(off.input);
      if (!Number.isFinite(ratio)) return <Text type='tertiary'>—</Text>;
      if (ratio < 0.995) {
        const savePct = Math.round((1 - ratio) * 100);
        return (
          <Tag color='green' shape='circle' size='large'>
            {t('省')} {savePct}%
          </Tag>
        );
      }
      return (
        <Tag color='amber' shape='circle' size='large'>
          {t('官方')} ×{ratio.toFixed(2)}
        </Tag>
      );
    },
  };

  return [modelNameColumn, paidColumn, officialColumn, discountColumn];
};

export default getGroupedPricingColumns;
