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
import { Card, Table, Tag, Typography, Skeleton, Empty } from '@douyinfe/semi-ui';
import { IllustrationNoResult, IllustrationNoResultDark } from '@douyinfe/semi-illustrations';
import { getLobeHubIcon } from '../../../../../helpers';
import { GROUP_ORDER, GROUP_META } from '../../../../../constants/officialPrices';
import { getGroupedPricingColumns } from './GroupedPricingColumns';

const { Text, Title } = Typography;

const GroupBlock = ({ group, models, groupRatio, usableGroup, t, columns }) => {
  const meta = GROUP_META[group] || {};
  const ratio = groupRatio[group];
  const desc = meta.desc || usableGroup[group] || '';
  const label = meta.label || usableGroup[group] || group;

  return (
    <Card
      className='!rounded-2xl mb-4'
      bodyStyle={{ padding: 0 }}
      header={
        <div className='flex items-start gap-3 px-4 py-3'>
          <div className='mt-1'>{getLobeHubIcon(meta.icon || 'Layers', 22)}</div>
          <div className='flex-1 min-w-0'>
            <div className='flex items-center gap-2 flex-wrap'>
              <Title heading={6} style={{ margin: 0 }}>
                {label}
              </Title>
              {meta.badge && (
                <Tag color={meta.accent || 'green'} shape='circle' size='small'>
                  {meta.badge}
                </Tag>
              )}
              {ratio !== undefined && ratio !== null && (
                <Tag color='white' shape='circle' size='small'>
                  {t('分组倍率')} {ratio}x
                </Tag>
              )}
              <Text type='tertiary' size='small'>
                {models.length} {t('个模型')}
              </Text>
            </div>
            {desc && (
              <Text type='tertiary' size='small' style={{ display: 'block', marginTop: 2 }}>
                {desc}
              </Text>
            )}
          </div>
        </div>
      }
    >
      <Table
        columns={columns}
        dataSource={models}
        pagination={false}
        size='small'
        rowKey='model_name'
      />
    </Card>
  );
};

const PricingGroupedView = (props) => {
  const {
    filteredModels = [],
    groupRatio = {},
    usableGroup = {},
    loading = false,
    t,
    copyText,
    currency,
    siteDisplayType,
    tokenUnit,
    displayPrice,
  } = props;

  const groupsToRender = useMemo(() => {
    // 展示顺序：先按 GROUP_ORDER，再补上后端新增但未登记顺序的组
    const known = GROUP_ORDER.filter((g) => groupRatio[g] !== undefined);
    const extra = Object.keys(groupRatio).filter(
      (g) => g !== '' && !known.includes(g),
    );
    return [...known, ...extra];
  }, [groupRatio]);

  const blocks = useMemo(() => {
    return groupsToRender
      .map((g) => ({
        group: g,
        models: filteredModels.filter(
          (m) => Array.isArray(m.enable_groups) && m.enable_groups.includes(g),
        ),
      }))
      .filter((b) => b.models.length > 0);
  }, [groupsToRender, filteredModels]);

  if (loading) {
    return (
      <div className='p-2'>
        {[0, 1, 2].map((i) => (
          <Card key={i} className='!rounded-2xl mb-4'>
            <Skeleton placeholder={<Skeleton.Paragraph rows={4} />} loading active />
          </Card>
        ))}
      </div>
    );
  }

  if (blocks.length === 0) {
    return (
      <div className='flex items-center justify-center py-16'>
        <Empty
          image={<IllustrationNoResult style={{ width: 140, height: 140 }} />}
          darkModeImage={<IllustrationNoResultDark style={{ width: 140, height: 140 }} />}
          description={t('没有匹配的模型')}
        />
      </div>
    );
  }

  return (
    <div className='p-2'>
      {blocks.map(({ group, models }) => (
        <GroupBlock
          key={group}
          group={group}
          models={models}
          groupRatio={groupRatio}
          usableGroup={usableGroup}
          t={t}
          columns={getGroupedPricingColumns({
            t,
            group,
            groupRatio,
            copyText,
            currency,
            siteDisplayType,
            tokenUnit,
            displayPrice,
          })}
        />
      ))}
    </div>
  );
};

export default PricingGroupedView;
