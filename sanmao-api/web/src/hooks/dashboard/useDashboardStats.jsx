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

import { useMemo } from 'react';
import { Wallet, Activity, Zap, Gauge } from 'lucide-react';
import {
  IconMoneyExchangeStroked,
  IconHistogram,
  IconCoinMoneyStroked,
  IconTextStroked,
  IconPulse,
  IconStopwatchStroked,
  IconTypograph,
  IconSend,
} from '@douyinfe/semi-icons';
import { renderQuota } from '../../helpers';
import { createSectionTitle } from '../../helpers/dashboard';

export const useDashboardStats = (
  userState,
  consumeQuota,
  consumeTokens,
  times,
  trendData,
  performanceMetrics,
  navigate,
  t,
  canViewBusinessOps = false,
) => {
  const businessCards = useMemo(() => {
    if (!canViewBusinessOps) return [];

    const quotaBalance = Number(userState?.user?.quota || 0);
    const quotaConsumed = Number(userState?.user?.used_quota || 0);
    const totalRequests = Number(userState?.user?.request_count || 0);
    const totalManagedQuota = quotaBalance + quotaConsumed;

    return [
      {
        title: createSectionTitle(Wallet, t('经营视角')),
        color: 'bg-emerald-50',
        items: [
          {
            title: t('剩余额度'),
            value: renderQuota(quotaBalance),
            icon: <IconMoneyExchangeStroked />,
            avatarColor: 'green',
            trendData: [],
            trendColor: '#10b981',
          },
          {
            title: t('已消耗额度'),
            value: renderQuota(quotaConsumed),
            hint: t('历史实际扣掉的钱'),
            icon: <IconHistogram />,
            avatarColor: 'cyan',
            trendData: trendData.consumeQuota,
            trendColor: '#06b6d4',
          },
        ],
      },
      {
        title: createSectionTitle(Zap, t('收入盘子')),
        color: 'bg-amber-50',
        items: [
          {
            title: t('已发放额度'),
            value: renderQuota(totalManagedQuota),
            hint: t('剩余额度 + 历史已消耗'),
            icon: <IconCoinMoneyStroked />,
            avatarColor: 'yellow',
            trendData: [],
            trendColor: '#f59e0b',
          },
          {
            title: t('总请求数'),
            value: isNaN(totalRequests) ? 0 : totalRequests.toLocaleString(),
            icon: <IconSend />,
            avatarColor: 'orange',
            trendData: trendData.times,
            trendColor: '#f97316',
          },
        ],
      },
    ];
  }, [
    canViewBusinessOps,
    userState?.user?.quota,
    userState?.user?.used_quota,
    userState?.user?.request_count,
    trendData.consumeQuota,
    trendData.times,
    t,
  ]);

  const groupedStatsData = useMemo(
    () => [
      ...businessCards,
      {
        title: createSectionTitle(Wallet, t('钱包额度')),
        color: 'bg-blue-50',
        items: [
          {
            title: t('剩余额度'),
            value: renderQuota(userState?.user?.quota),
            icon: <IconMoneyExchangeStroked />,
            avatarColor: 'blue',
            trendData: [],
            trendColor: '#3b82f6',
          },
          {
            title: t('历史已消耗'),
            value: renderQuota(userState?.user?.used_quota),
            icon: <IconHistogram />,
            avatarColor: 'purple',
            trendData: [],
            trendColor: '#8b5cf6',
          },
        ],
      },
      {
        title: createSectionTitle(Activity, t('调用统计')),
        color: 'bg-green-50',
        items: [
          {
            title: t('历史请求数'),
            value: userState.user?.request_count,
            icon: <IconSend />,
            avatarColor: 'green',
            trendData: [],
            trendColor: '#10b981',
          },
          {
            title: t('本周期调用数'),
            value: times,
            icon: <IconPulse />,
            avatarColor: 'cyan',
            trendData: trendData.times,
            trendColor: '#06b6d4',
          },
        ],
      },
      {
        title: createSectionTitle(Zap, t('本周期消耗')),
        color: 'bg-yellow-50',
        items: [
          {
            title: t('已消耗额度'),
            value: renderQuota(consumeQuota),
            icon: <IconCoinMoneyStroked />,
            avatarColor: 'yellow',
            trendData: trendData.consumeQuota,
            trendColor: '#f59e0b',
          },
          {
            title: t('消耗 Tokens'),
            value: isNaN(consumeTokens) ? 0 : consumeTokens.toLocaleString(),
            icon: <IconTextStroked />,
            avatarColor: 'pink',
            trendData: trendData.tokens,
            trendColor: '#ec4899',
          },
        ],
      },
      {
        title: createSectionTitle(Gauge, t('实时速度')),
        color: 'bg-indigo-50',
        items: [
          {
            title: t('近一分钟请求/分'),
            value: performanceMetrics.avgRPM,
            hint: t('最近一分钟每分钟请求数'),
            icon: <IconStopwatchStroked />,
            avatarColor: 'indigo',
            trendData: trendData.rpm,
            trendColor: '#6366f1',
          },
          {
            title: t('近一分钟Token/分'),
            value: performanceMetrics.avgTPM,
            hint: t('最近一分钟每分钟 Token 数'),
            icon: <IconTypograph />,
            avatarColor: 'orange',
            trendData: trendData.tpm,
            trendColor: '#f97316',
          },
        ],
      },
    ],
    [
      businessCards,
      userState?.user?.quota,
      userState?.user?.used_quota,
      userState?.user?.request_count,
      times,
      consumeQuota,
      consumeTokens,
      trendData,
      performanceMetrics,
      navigate,
      t,
    ],
  );

  return {
    groupedStatsData,
  };
};
