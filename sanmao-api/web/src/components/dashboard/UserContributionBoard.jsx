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
import { Card, Table, Skeleton, Typography, Tag } from '@douyinfe/semi-ui';
import { renderNumber, renderQuota } from '../../helpers';

const { Text } = Typography;

// 净赚系数：所有分组定价 = 上游成本 ×1.3，故我赚的 ≈ 消费 × 0.3 / 1.3
const NET_PROFIT_FACTOR = 0.3 / 1.3;

const safeQuota = (q, digits = 2) => {
  const formatted = renderQuota(Number(q || 0), digits);
  if (String(formatted).includes('NaN')) {
    return `${renderNumber(Number(q || 0))}`;
  }
  return formatted;
};

const rankTagColor = (idx) => {
  if (idx === 0) return 'amber';
  if (idx === 1) return 'grey';
  if (idx === 2) return 'orange';
  return 'white';
};

const UserContributionBoard = ({ loading, userRank = [], t }) => {
  const rows = useMemo(
    () =>
      (userRank || []).map((r, i) => ({
        key: r.username || String(i),
        idx: i,
        username: r.username || '-',
        total_quota: Number(r.total_quota || 0),
        recent_quota: Number(r.recent_quota || 0),
        count: Number(r.count || 0),
        net: Number(r.total_quota || 0) * NET_PROFIT_FACTOR,
      })),
    [userRank],
  );

  const columns = [
    {
      title: t('排名'),
      dataIndex: 'idx',
      width: 72,
      render: (v) => (
        <Tag color={rankTagColor(v)} shape='circle'>
          {v + 1}
        </Tag>
      ),
    },
    {
      title: t('用户'),
      dataIndex: 'username',
      render: (v) => <Text strong>{v}</Text>,
    },
    {
      title: t('总消费'),
      dataIndex: 'total_quota',
      sorter: (a, b) => a.total_quota - b.total_quota,
      render: (v) => <Text>{safeQuota(v)}</Text>,
    },
    {
      title: t('近7天'),
      dataIndex: 'recent_quota',
      sorter: (a, b) => a.recent_quota - b.recent_quota,
      render: (v) => <Text type='tertiary'>{safeQuota(v)}</Text>,
    },
    {
      title: t('调用次数'),
      dataIndex: 'count',
      sorter: (a, b) => a.count - b.count,
      render: (v) => <Text type='tertiary'>{renderNumber(v)}</Text>,
    },
    {
      title: t('我赚了'),
      dataIndex: 'net',
      sorter: (a, b) => a.net - b.net,
      render: (v) => (
        <Text style={{ color: 'var(--semi-color-success)', fontWeight: 600 }}>
          {safeQuota(v)}
        </Text>
      ),
    },
  ];

  return (
    <Card
      className='mb-4 !rounded-2xl'
      title={
        <div className='flex items-center justify-between'>
          <span style={{ fontWeight: 700 }}>{t('用户贡献榜')}</span>
          <Text type='tertiary' size='small'>
            {t('谁最挺你 · 按总消费排名')}
          </Text>
        </div>
      }
    >
      {loading ? (
        <Skeleton placeholder={<Skeleton.Paragraph rows={5} />} loading />
      ) : (
        <Table
          columns={columns}
          dataSource={rows}
          pagination={
            rows.length > 10 ? { pageSize: 10, showSizeChanger: false } : false
          }
          size='small'
          empty={t('暂无消费记录')}
        />
      )}
    </Card>
  );
};

export default UserContributionBoard;
