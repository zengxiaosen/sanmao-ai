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

import { useState, useCallback, useEffect } from 'react';
import { initVChartSemiTheme } from '@visactor/vchart-semi-theme';
import { DASHBOARD_CHART_BASE_SPEC } from '../../constants/dashboard.constants';
import {
  modelColorMap,
  renderNumber,
  renderQuota,
  modelToColor,
  getQuotaWithUnit,
} from '../../helpers';
import {
  processRawData,
  calculateTrendData,
  aggregateDataByTimeAndModel,
  generateChartTimePoints,
  updateChartSpec,
  updateMapValue,
  initializeMaps,
} from '../../helpers/dashboard';
import { buildChannelAnalysisView } from '../../helpers/channelAnalytics';

export const useDashboardCharts = (
  dataExportDefaultTime,
  setTrendData,
  setConsumeQuota,
  setTimes,
  setConsumeTokens,
  setPieData,
  setLineData,
  setModelColors,
  t,
) => {
  // ========== 图表规格状态 ==========
  const [spec_pie, setSpecPie] = useState({
    ...DASHBOARD_CHART_BASE_SPEC,
    type: 'pie',
    data: [
      {
        id: 'id0',
        values: [{ type: 'null', value: '0' }],
      },
    ],
    outerRadius: 0.8,
    innerRadius: 0.5,
    padAngle: 0.6,
    valueField: 'value',
    categoryField: 'type',
    pie: {
      style: {
        cornerRadius: 10,
      },
      state: {
        hover: {
          outerRadius: 0.85,
          stroke: '#000',
          lineWidth: 1,
        },
        selected: {
          outerRadius: 0.85,
          stroke: '#000',
          lineWidth: 1,
        },
      },
    },
    title: {
      visible: true,
      text: t('模型调用次数占比'),
      subtext: `${t('总计')}：${renderNumber(0)}`,
    },
    legends: {
      visible: true,
      orient: 'left',
    },
    label: {
      visible: true,
    },
    tooltip: {
      mark: {
        content: [
          {
            key: (datum) => datum['type'],
            value: (datum) => renderNumber(datum['value']),
          },
        ],
      },
    },
    color: {
      specified: modelColorMap,
    },
  });

  const [spec_line, setSpecLine] = useState({
    ...DASHBOARD_CHART_BASE_SPEC,
    type: 'bar',
    data: [
      {
        id: 'barData',
        values: [],
      },
    ],
    xField: 'Time',
    yField: 'Usage',
    seriesField: 'Model',
    stack: true,
    legends: {
      visible: true,
      selectMode: 'single',
    },
    title: {
      visible: true,
      text: t('模型收入分布'),
      subtext: `${t('总计')}：${renderQuota(0, 2)}`,
    },
    bar: {
      state: {
        hover: {
          stroke: '#000',
          lineWidth: 1,
        },
      },
    },
    tooltip: {
      mark: {
        content: [
          {
            key: (datum) => datum['Model'],
            value: (datum) => renderQuota(datum['rawQuota'] || 0, 4),
          },
        ],
      },
      dimension: {
        content: [
          {
            key: (datum) => datum['Model'],
            value: (datum) => datum['rawQuota'] || 0,
          },
        ],
        updateContent: (array) => {
          array.sort((a, b) => b.value - a.value);
          let sum = 0;
          for (let i = 0; i < array.length; i++) {
            if (array[i].key == '其他') {
              continue;
            }
            let value = parseFloat(array[i].value);
            if (isNaN(value)) {
              value = 0;
            }
            if (array[i].datum && array[i].datum.TimeSum) {
              sum = array[i].datum.TimeSum;
            }
            array[i].value = renderQuota(value, 4);
          }
          array.unshift({
            key: t('总计'),
            value: renderQuota(sum, 4),
          });
          return array;
        },
      },
    },
    color: {
      specified: modelColorMap,
    },
  });

  // 模型收入趋势折线图
  const [spec_model_line, setSpecModelLine] = useState({
    ...DASHBOARD_CHART_BASE_SPEC,
    type: 'line',
    data: [
      {
        id: 'lineData',
        values: [],
      },
    ],
    xField: 'Time',
    yField: 'Count',
    seriesField: 'Model',
    legends: {
      visible: true,
      selectMode: 'single',
    },
    title: {
      visible: true,
      text: t('模型收入趋势'),
      subtext: '',
    },
    tooltip: {
      mark: {
        content: [
          {
            key: (datum) => datum['Model'],
            value: (datum) => renderNumber(datum['Count']),
          },
        ],
      },
    },
    color: {
      specified: modelColorMap,
    },
  });

  // 模型调用次数排行柱状图
  const [spec_rank_bar, setSpecRankBar] = useState({
    ...DASHBOARD_CHART_BASE_SPEC,
    type: 'bar',
    data: [
      {
        id: 'rankData',
        values: [],
      },
    ],
    xField: 'Model',
    yField: 'Count',
    seriesField: 'Model',
    legends: {
      visible: true,
      selectMode: 'single',
    },
    title: {
      visible: true,
      text: t('模型调用次数排行'),
      subtext: '',
    },
    bar: {
      state: {
        hover: {
          stroke: '#000',
          lineWidth: 1,
        },
      },
    },
    tooltip: {
      mark: {
        content: [
          {
            key: (datum) => datum['Model'],
            value: (datum) => renderNumber(datum['Count']),
          },
        ],
      },
    },
    color: {
      specified: modelColorMap,
    },
  });

  const [spec_channel_requests_bar, setSpecChannelRequestsBar] = useState({
    ...DASHBOARD_CHART_BASE_SPEC,
    type: 'bar',
    data: [
      {
        id: 'channelRequestsData',
        values: [],
      },
    ],
    xField: 'Channel',
    yField: 'Count',
    seriesField: 'Channel',
    legends: {
      visible: true,
      selectMode: 'single',
    },
    title: {
      visible: true,
      text: t('24h 渠道调用次数排行'),
      subtext: `${t('总计')}：${renderNumber(0)}`,
    },
    tooltip: {
      mark: {
        content: [
          {
            key: (datum) => datum['Channel'],
            value: (datum) => renderNumber(datum['Count']),
          },
        ],
      },
    },
  });

  const [spec_channel_quota_bar, setSpecChannelQuotaBar] = useState({
    ...DASHBOARD_CHART_BASE_SPEC,
    type: 'bar',
    data: [
      {
        id: 'channelQuotaData',
        values: [],
      },
    ],
    xField: 'Channel',
    yField: 'Quota',
    seriesField: 'Channel',
    legends: {
      visible: true,
      selectMode: 'single',
    },
    title: {
      visible: true,
      text: t('24h 渠道收入排行'),
      subtext: `${t('总计')}：${renderQuota(0, 2)}`,
    },
    tooltip: {
      mark: {
        content: [
          {
            key: (datum) => datum['Channel'],
            value: (datum) => renderQuota(datum['rawQuota'] || 0, 4),
          },
          {
            key: t('调用次数'),
            value: (datum) => renderNumber(datum['Count'] || 0),
          },
          {
            key: 'Tokens',
            value: (datum) => renderNumber(datum['Tokens'] || 0),
          },
        ],
      },
    },
  });

  const [spec_channel_model_bar, setSpecChannelModelBar] = useState({
    ...DASHBOARD_CHART_BASE_SPEC,
    type: 'bar',
    data: [
      {
        id: 'channelModelData',
        values: [],
      },
    ],
    xField: 'Label',
    yField: 'Quota',
    seriesField: 'Channel',
    legends: {
      visible: true,
      selectMode: 'single',
    },
    title: {
      visible: true,
      text: t('渠道下模型分布'),
      subtext: '',
    },
    tooltip: {
      mark: {
        content: [
          {
            key: (datum) => datum['Label'],
            value: (datum) => renderQuota(datum['rawQuota'] || 0, 4),
          },
          {
            key: t('调用次数'),
            value: (datum) => renderNumber(datum['Count'] || 0),
          },
        ],
      },
    },
  });

  const [spec_model_channel_bar, setSpecModelChannelBar] = useState({
    ...DASHBOARD_CHART_BASE_SPEC,
    type: 'bar',
    data: [
      {
        id: 'modelChannelData',
        values: [],
      },
    ],
    xField: 'Label',
    yField: 'Quota',
    seriesField: 'Model',
    legends: {
      visible: true,
      selectMode: 'single',
    },
    title: {
      visible: true,
      text: t('模型下渠道分布'),
      subtext: '',
    },
    tooltip: {
      mark: {
        content: [
          {
            key: (datum) => datum['Label'],
            value: (datum) => renderQuota(datum['rawQuota'] || 0, 4),
          },
          {
            key: t('调用次数'),
            value: (datum) => renderNumber(datum['Count'] || 0),
          },
        ],
      },
    },
  });

  const [channelAnalysisRows, setChannelAnalysisRows] = useState([]);

  // ========== 数据处理函数 ==========
  const generateModelColors = useCallback((uniqueModels, modelColors) => {
    const newModelColors = {};
    Array.from(uniqueModels).forEach((modelName) => {
      newModelColors[modelName] =
        modelColorMap[modelName] ||
        modelColors[modelName] ||
        modelToColor(modelName);
    });
    return newModelColors;
  }, []);

  const updateChartData = useCallback(
    (data) => {
      const processedData = processRawData(
        data,
        dataExportDefaultTime,
        initializeMaps,
        updateMapValue,
      );

      const {
        totalQuota,
        totalTimes,
        totalTokens,
        uniqueModels,
        timePoints,
        timeQuotaMap,
        timeTokensMap,
        timeCountMap,
      } = processedData;

      const trendDataResult = calculateTrendData(
        timePoints,
        timeQuotaMap,
        timeTokensMap,
        timeCountMap,
        dataExportDefaultTime,
      );
      setTrendData(trendDataResult);

      const newModelColors = generateModelColors(uniqueModels, {});
      setModelColors(newModelColors);

      const aggregatedData = aggregateDataByTimeAndModel(
        data,
        dataExportDefaultTime,
      );

      const modelTotals = new Map();
      for (let [_, value] of aggregatedData) {
        updateMapValue(modelTotals, value.model, value.count);
      }

      const newPieData = Array.from(modelTotals)
        .map(([model, count]) => ({
          type: model,
          value: count,
        }))
        .sort((a, b) => b.value - a.value);

      const chartTimePoints = generateChartTimePoints(
        aggregatedData,
        data,
        dataExportDefaultTime,
      );

      let newLineData = [];

      chartTimePoints.forEach((time) => {
        let timeData = Array.from(uniqueModels).map((model) => {
          const key = `${time}-${model}`;
          const aggregated = aggregatedData.get(key);
          return {
            Time: time,
            Model: model,
            rawQuota: aggregated?.quota || 0,
            Usage: aggregated?.quota
              ? getQuotaWithUnit(aggregated.quota, 4)
              : 0,
          };
        });

        const timeSum = timeData.reduce((sum, item) => sum + item.rawQuota, 0);
        timeData.sort((a, b) => b.rawQuota - a.rawQuota);
        timeData = timeData.map((item) => ({ ...item, TimeSum: timeSum }));
        newLineData.push(...timeData);
      });

      newLineData.sort((a, b) => a.Time.localeCompare(b.Time));

      updateChartSpec(
        setSpecPie,
        newPieData,
        `${t('总计')}：${renderNumber(totalTimes)}`,
        newModelColors,
        'id0',
      );

      updateChartSpec(
        setSpecLine,
        newLineData,
        `${t('总计')}：${renderQuota(totalQuota, 2)}`,
        newModelColors,
        'barData',
      );

      // ===== 模型调用次数折线图 =====
      let modelLineData = [];
      chartTimePoints.forEach((time) => {
        const timeData = Array.from(uniqueModels).map((model) => {
          const key = `${time}-${model}`;
          const aggregated = aggregatedData.get(key);
          return {
            Time: time,
            Model: model,
            Count: aggregated?.count || 0,
          };
        });
        modelLineData.push(...timeData);
      });
      modelLineData.sort((a, b) => a.Time.localeCompare(b.Time));

      // ===== 模型调用次数排行柱状图 =====
      const rankData = Array.from(modelTotals)
        .map(([model, count]) => ({
          Model: model,
          Count: count,
        }))
        .sort((a, b) => b.Count - a.Count);

      updateChartSpec(
        setSpecModelLine,
        modelLineData,
        `${t('总计')}：${renderNumber(totalTimes)}`,
        newModelColors,
        'lineData',
      );

      updateChartSpec(
        setSpecRankBar,
        rankData,
        `${t('总计')}：${renderNumber(totalTimes)}`,
        newModelColors,
        'rankData',
      );

      setPieData(newPieData);
      setLineData(newLineData);
      setConsumeQuota(totalQuota);
      setTimes(totalTimes);
      setConsumeTokens(totalTokens);
    },
    [
      dataExportDefaultTime,
      setTrendData,
      generateModelColors,
      setModelColors,
      setPieData,
      setLineData,
      setConsumeQuota,
      setTimes,
      setConsumeTokens,
      t,
    ],
  );

  const updateChannelChartData = useCallback(
    (
      channelItems = [],
      channelModelItems = [],
      window = '24h',
      selectedModel = '',
      selectedChannel = '',
      topN = 10,
    ) => {
      const windowLabel =
        window === 'today' ? t('本天') : window === 'week' ? t('本周') : '24h';
      const {
        channelRequestData,
        channelQuotaData,
        channelModelData,
        modelChannelData,
        detailRows,
        totalRequests,
        totalQuota,
      } = buildChannelAnalysisView({
        channelItems,
        channelModelItems,
        selectedModel,
        selectedChannel,
        topN,
      });

      setSpecChannelRequestsBar((prev) => ({
        ...prev,
        data: [{ id: 'channelRequestsData', values: channelRequestData }],
        title: {
          ...prev.title,
          text: `${windowLabel} ${t('渠道调用次数排行')}`,
          subtext: `${t('总计')}：${renderNumber(totalRequests)}`,
        },
      }));

      setSpecChannelQuotaBar((prev) => ({
        ...prev,
        data: [{ id: 'channelQuotaData', values: channelQuotaData }],
        title: {
          ...prev.title,
          text: `${windowLabel} ${t('渠道消耗排行')}`,
          subtext: `${t('总计')}：${renderQuota(totalQuota, 2)}`,
        },
      }));

      setSpecChannelModelBar((prev) => ({
        ...prev,
        data: [{ id: 'channelModelData', values: channelModelData }],
        title: {
          ...prev.title,
          text: `${windowLabel} ${t('渠道下模型分布')}`,
          subtext: `${t('Top 20')}`,
        },
      }));

      setSpecModelChannelBar((prev) => ({
        ...prev,
        data: [{ id: 'modelChannelData', values: modelChannelData }],
        title: {
          ...prev.title,
          text: `${windowLabel} ${t('模型下渠道分布')}`,
          subtext: `${t('Top 20')}`,
        },
      }));
      setChannelAnalysisRows(detailRows);
    },
    [t],
  );

  // ========== 初始化图表主题 ==========
  useEffect(() => {
    initVChartSemiTheme({
      isWatchingThemeSwitch: true,
    });
  }, []);

  return {
    // 图表规格
    spec_pie,
    spec_line,
    spec_model_line,
    spec_rank_bar,
    spec_channel_requests_bar,
    spec_channel_quota_bar,
    spec_channel_model_bar,
    spec_model_channel_bar,
    channelAnalysisRows,

    // 函数
    updateChartData,
    updateChannelChartData,
    generateModelColors,
  };
};
