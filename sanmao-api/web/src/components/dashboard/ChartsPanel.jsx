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
import {
  Card,
  Radio,
  RadioGroup,
  Select,
  Table,
  Tabs,
  TabPane,
} from '@douyinfe/semi-ui';
import { PieChart } from 'lucide-react';
import { VChart } from '@visactor/react-vchart';
import { renderNumber, renderQuota, selectFilter } from '../../helpers';

const ChartsPanel = ({
  activeChartTab,
  setActiveChartTab,
  spec_line,
  spec_model_line,
  spec_pie,
  spec_rank_bar,
  spec_channel_requests_bar,
  spec_channel_quota_bar,
  spec_channel_model_bar,
  spec_model_channel_bar,
  channelUsageWindow,
  setChannelUsageWindow,
  onChannelUsageWindowChange,
  channelAnalysisTopN,
  setChannelAnalysisTopN,
  selectedAnalysisModel,
  setSelectedAnalysisModel,
  selectedAnalysisChannel,
  setSelectedAnalysisChannel,
  onChannelBarClick,
  onChannelModelBarClick,
  onModelChannelBarClick,
  modelOptions,
  channelOptions,
  channelAnalysisRows,
  CARD_PROPS,
  CHART_CONFIG,
  FLEX_CENTER_GAP2,
  hasApiInfoPanel,
  t,
}) => {
  return (
    <Card
      {...CARD_PROPS}
      className={`!rounded-2xl ${hasApiInfoPanel ? 'lg:col-span-3' : ''}`}
      title={
        <div className='flex flex-col lg:flex-row lg:items-center lg:justify-between w-full gap-3'>
          <div className={FLEX_CENTER_GAP2}>
            <PieChart size={16} />
            {t('模型数据分析')}
          </div>
          <Tabs
            type='slash'
            activeKey={activeChartTab}
            onChange={setActiveChartTab}
          >
            <TabPane tab={<span>{t('消费分布')}</span>} itemKey='1' />
            <TabPane tab={<span>{t('消费趋势')}</span>} itemKey='2' />
            <TabPane tab={<span>{t('调用次数分布')}</span>} itemKey='3' />
            <TabPane tab={<span>{t('调用次数排行')}</span>} itemKey='4' />
            <TabPane tab={<span>{t('调用来源')}</span>} itemKey='5' />
          </Tabs>
        </div>
      }
      bodyStyle={{ padding: 0 }}
    >
      <div className={activeChartTab === '5' ? 'min-h-[520px] p-2' : 'h-96 p-2'}>
        {activeChartTab === '1' && (
          <VChart spec={spec_line} option={CHART_CONFIG} />
        )}
        {activeChartTab === '2' && (
          <VChart spec={spec_model_line} option={CHART_CONFIG} />
        )}
        {activeChartTab === '3' && (
          <VChart spec={spec_pie} option={CHART_CONFIG} />
        )}
        {activeChartTab === '4' && (
          <VChart spec={spec_rank_bar} option={CHART_CONFIG} />
        )}
        {activeChartTab === '5' && (
          <div className='h-full flex flex-col gap-3'>
            <div className='flex flex-col lg:flex-row lg:items-center lg:justify-end gap-2 px-2'>
              <Select
                value={channelAnalysisTopN}
                optionList={[5, 10, 20].map((value) => ({
                  label: `Top ${value}`,
                  value,
                }))}
                onChange={setChannelAnalysisTopN}
                style={{ width: 110 }}
              />
              <RadioGroup
                type='button'
                buttonSize='small'
                value={channelUsageWindow}
                onChange={(event) => {
                  const nextWindow = event.target.value;
                  setChannelUsageWindow(nextWindow);
                  onChannelUsageWindowChange?.(nextWindow);
                }}
              >
                <Radio value='24h'>{t('24h')}</Radio>
                <Radio value='today'>{t('本天')}</Radio>
                <Radio value='week'>{t('本周')}</Radio>
              </RadioGroup>
            </div>
            <div className='grid grid-cols-1 lg:grid-cols-2 gap-2 flex-1 min-h-0'>
              <div className='flex flex-col gap-2'>
                <VChart
                  spec={spec_channel_requests_bar}
                  option={CHART_CONFIG}
                  onClick={onChannelBarClick}
                />
                <VChart
                  spec={spec_channel_quota_bar}
                  option={CHART_CONFIG}
                  onClick={onChannelBarClick}
                />
              </div>
              <div className='flex flex-col gap-3'>
                <div className='grid grid-cols-1 gap-3'>
                  <div>
                    <div className='text-xs text-gray-500 mb-1'>
                      {t('模型 -> 渠道')}
                    </div>
                    <Select
                      value={selectedAnalysisModel}
                      optionList={modelOptions}
                      onChange={setSelectedAnalysisModel}
                      filter={selectFilter}
                      autoClearSearchValue={false}
                      placeholder={t('选择模型')}
                    />
                  </div>
                  <div className='h-40'>
                    <VChart
                      spec={spec_model_channel_bar}
                      option={CHART_CONFIG}
                      onClick={onModelChannelBarClick}
                    />
                  </div>
                  <div>
                    <div className='text-xs text-gray-500 mb-1'>
                      {t('渠道 -> 模型')}
                    </div>
                    <Select
                      value={selectedAnalysisChannel}
                      optionList={channelOptions}
                      onChange={setSelectedAnalysisChannel}
                      filter={selectFilter}
                      autoClearSearchValue={false}
                      placeholder={t('选择渠道')}
                    />
                  </div>
                  <div className='h-40'>
                    <VChart
                      spec={spec_channel_model_bar}
                      option={CHART_CONFIG}
                      onClick={onChannelModelBarClick}
                    />
                  </div>
                </div>
              </div>
            </div>
            <Table
              size='small'
              pagination={false}
              dataSource={channelAnalysisRows}
              columns={[
                { title: '#', dataIndex: 'rank', width: 48 },
                {
                  title: t('渠道'),
                  dataIndex: 'channel',
                  sorter: (a, b) => a.channel.localeCompare(b.channel),
                },
                {
                  title: t('模型'),
                  dataIndex: 'model',
                  sorter: (a, b) => a.model.localeCompare(b.model),
                },
                {
                  title: t('调用次数'),
                  dataIndex: 'count',
                  sorter: (a, b) => (a.count || 0) - (b.count || 0),
                  render: (value) => renderNumber(value || 0),
                },
                {
                  title: t('收入'),
                  dataIndex: 'quota',
                  sorter: (a, b) => (a.quota || 0) - (b.quota || 0),
                  render: (value) => renderQuota(value || 0, 4),
                },
                {
                  title: 'Tokens',
                  dataIndex: 'tokens',
                  sorter: (a, b) => (a.tokens || 0) - (b.tokens || 0),
                  render: (value) => renderNumber(value || 0),
                },
              ]}
            />
          </div>
        )}
      </div>
    </Card>
  );
};

export default ChartsPanel;
