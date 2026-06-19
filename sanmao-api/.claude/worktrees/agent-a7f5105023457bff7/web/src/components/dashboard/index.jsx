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

import React, { useContext, useEffect, useMemo } from 'react';
import { getRelativeTime } from '../../helpers';
import { UserContext } from '../../context/User';
import { StatusContext } from '../../context/Status';

import DashboardHeader from './DashboardHeader';
import StatsCards from './StatsCards';
import ChartsPanel from './ChartsPanel';
import ApiInfoPanel from './ApiInfoPanel';
import AnnouncementsPanel from './AnnouncementsPanel';
import FaqPanel from './FaqPanel';
import UptimePanel from './UptimePanel';
import SearchModal from './modals/SearchModal';
import BusinessSummaryPanel from './BusinessSummaryPanel';

import { useDashboardData } from '../../hooks/dashboard/useDashboardData';
import { useDashboardStats } from '../../hooks/dashboard/useDashboardStats';
import { useDashboardCharts } from '../../hooks/dashboard/useDashboardCharts';

import {
  CHART_CONFIG,
  CARD_PROPS,
  FLEX_CENTER_GAP2,
  ILLUSTRATION_SIZE,
  ANNOUNCEMENT_LEGEND_DATA,
  UPTIME_STATUS_MAP,
} from '../../constants/dashboard.constants';
import {
  getTrendSpec,
  handleCopyUrl,
  handleSpeedTest,
  getUptimeStatusColor,
  getUptimeStatusText,
  renderMonitorList,
} from '../../helpers/dashboard';

const Dashboard = () => {
  // ========== Context ==========
  const [userState, userDispatch] = useContext(UserContext);
  const [statusState, statusDispatch] = useContext(StatusContext);

  // ========== 主要数据管理 ==========
  const dashboardData = useDashboardData(userState, userDispatch, statusState);

  // ========== 图表管理 ==========
  const dashboardCharts = useDashboardCharts(
    dashboardData.dataExportDefaultTime,
    dashboardData.setTrendData,
    dashboardData.setConsumeQuota,
    dashboardData.setTimes,
    dashboardData.setConsumeTokens,
    dashboardData.setPieData,
    dashboardData.setLineData,
    dashboardData.setModelColors,
    dashboardData.t,
  );

  // ========== 统计数据 ==========
  const { groupedStatsData } = useDashboardStats(
    userState,
    dashboardData.consumeQuota,
    dashboardData.consumeTokens,
    dashboardData.times,
    dashboardData.trendData,
    dashboardData.performanceMetrics,
    dashboardData.navigate,
    dashboardData.t,
    dashboardData.canViewBusinessOps,
  );

  // ========== 数据处理 ==========
  const initChart = async () => {
    await dashboardData.loadQuotaData().then((data) => {
      if (data && data.length > 0) {
        dashboardCharts.updateChartData(data);
      }
    });
    await dashboardData.loadChannelUsageData().then((channelData) => {
      dashboardCharts.updateChannelChartData(
        channelData?.channelItems || [],
        channelData?.channelModelItems || [],
        dashboardData.channelUsageWindow,
        channelData?.selectedModel || dashboardData.selectedAnalysisModel,
        channelData?.selectedChannel || dashboardData.selectedAnalysisChannel,
        dashboardData.channelAnalysisTopN,
      );
    });
    await dashboardData.loadBusinessStats();
    await dashboardData.loadUptimeData();
  };

  const handleRefresh = async () => {
    const result = await dashboardData.refresh();
    if (result?.quotaData && result.quotaData.length > 0) {
      dashboardCharts.updateChartData(result.quotaData);
    }
    dashboardCharts.updateChannelChartData(
      result?.channelData?.channelItems || [],
      result?.channelData?.channelModelItems || [],
      dashboardData.channelUsageWindow,
      result?.channelData?.selectedModel || dashboardData.selectedAnalysisModel,
      result?.channelData?.selectedChannel || dashboardData.selectedAnalysisChannel,
      dashboardData.channelAnalysisTopN,
    );
  };

  const handleSearchConfirm = async () => {
    const result = await dashboardData.handleSearchConfirm(
      dashboardCharts.updateChartData,
    );
    dashboardCharts.updateChannelChartData(
      result?.channelData?.channelItems || [],
      result?.channelData?.channelModelItems || [],
      dashboardData.channelUsageWindow,
      result?.channelData?.selectedModel || dashboardData.selectedAnalysisModel,
      result?.channelData?.selectedChannel || dashboardData.selectedAnalysisChannel,
      dashboardData.channelAnalysisTopN,
    );
  };

  const handleChannelUsageWindowChange = async (window) => {
    const channelData = await dashboardData.loadChannelUsageData(window);
    dashboardCharts.updateChannelChartData(
      channelData?.channelItems || [],
      channelData?.channelModelItems || [],
      window,
      channelData?.selectedModel || dashboardData.selectedAnalysisModel,
      channelData?.selectedChannel || dashboardData.selectedAnalysisChannel,
      dashboardData.channelAnalysisTopN,
    );
  };

  const modelOptions = useMemo(() => {
    const names = Array.from(
      new Set(
        (dashboardData.channelModelUsageData || [])
          .map((item) => item.model_name)
          .filter(Boolean),
      ),
    );
    return names.map((name) => ({ label: name, value: name }));
  }, [dashboardData.channelModelUsageData]);

  const channelOptions = useMemo(() => {
    return (dashboardData.channelUsageData || []).map((item) => ({
      label: item.channel_name || `#${item.channel_id}`,
      value: String(item.channel_id),
    }));
  }, [dashboardData.channelUsageData]);

  const handleChannelBarClick = (event) => {
    const datum = event?.datum?.[0] || event?.datum;
    const channelId =
      datum?.channelId ||
      (datum?.Channel
        ? channelOptions.find((item) => item.label === datum.Channel)?.value
        : '');
    if (channelId) {
      dashboardData.setSelectedAnalysisChannel(String(channelId));
    }
  };

  const handleChannelModelBarClick = (event) => {
    const datum = event?.datum?.[0] || event?.datum;
    const modelName = datum?.Model || datum?.Label;
    if (modelName) {
      dashboardData.setSelectedAnalysisModel(modelName);
    }
  };

  const handleModelChannelBarClick = (event) => {
    const datum = event?.datum?.[0] || event?.datum;
    const channelId =
      datum?.channelId ||
      (datum?.Channel
        ? channelOptions.find((item) => item.label === datum.Channel)?.value
        : '');
    if (channelId) {
      dashboardData.setSelectedAnalysisChannel(String(channelId));
    }
  };

  useEffect(() => {
    dashboardCharts.updateChannelChartData(
      dashboardData.channelUsageData,
      dashboardData.channelModelUsageData,
      dashboardData.channelUsageWindow,
      dashboardData.selectedAnalysisModel,
      dashboardData.selectedAnalysisChannel,
      dashboardData.channelAnalysisTopN,
    );
  }, [
    dashboardData.channelUsageData,
    dashboardData.channelModelUsageData,
    dashboardData.channelUsageWindow,
    dashboardData.selectedAnalysisModel,
    dashboardData.selectedAnalysisChannel,
    dashboardData.channelAnalysisTopN,
  ]);

  // ========== 数据准备 ==========
  const apiInfoData = statusState?.status?.api_info || [];
  const announcementData = (statusState?.status?.announcements || []).map(
    (item) => {
      const pubDate = item?.publishDate ? new Date(item.publishDate) : null;
      const absoluteTime =
        pubDate && !isNaN(pubDate.getTime())
          ? `${pubDate.getFullYear()}-${String(pubDate.getMonth() + 1).padStart(2, '0')}-${String(pubDate.getDate()).padStart(2, '0')} ${String(pubDate.getHours()).padStart(2, '0')}:${String(pubDate.getMinutes()).padStart(2, '0')}`
          : item?.publishDate || '';
      const relativeTime = getRelativeTime(item.publishDate);
      return {
        ...item,
        time: absoluteTime,
        relative: relativeTime,
      };
    },
  );
  const faqData = statusState?.status?.faq || [];

  const uptimeLegendData = Object.entries(UPTIME_STATUS_MAP).map(
    ([status, info]) => ({
      status: Number(status),
      color: info.color,
      label: dashboardData.t(info.label),
    }),
  );

  // ========== Effects ==========
  useEffect(() => {
    initChart();
  }, []);

  return (
    <div className='h-full'>
      <DashboardHeader
        getGreeting={dashboardData.getGreeting}
        greetingVisible={dashboardData.greetingVisible}
        showSearchModal={dashboardData.showSearchModal}
        refresh={handleRefresh}
        loading={dashboardData.loading}
        t={dashboardData.t}
      />

      <SearchModal
        searchModalVisible={dashboardData.searchModalVisible}
        handleSearchConfirm={handleSearchConfirm}
        handleCloseModal={dashboardData.handleCloseModal}
        isMobile={dashboardData.isMobile}
        isAdminUser={dashboardData.isAdminUser}
        inputs={dashboardData.inputs}
        dataExportDefaultTime={dashboardData.dataExportDefaultTime}
        timeOptions={dashboardData.timeOptions}
        handleInputChange={dashboardData.handleInputChange}
        t={dashboardData.t}
      />

      {dashboardData.canViewBusinessOps && (
        <BusinessSummaryPanel
          loading={dashboardData.loading}
          consumeQuota={dashboardData.businessStats.quota}
          consumeTokens={dashboardData.businessStats.tokens}
          times={dashboardData.businessStats.count}
          upstreamCostQuota={dashboardData.businessStats.upstreamCostQuota}
          usageCostQuota={dashboardData.businessStats.usageCostQuota}
          fixedCostQuota={dashboardData.businessStats.fixedCostQuota}
          netProfitQuota={dashboardData.businessStats.netProfitQuota}
          profitRate={dashboardData.businessStats.profitRate}
          costConfigured={dashboardData.businessStats.costConfigured}
          costConfiguredLogs={dashboardData.businessStats.costConfiguredLogs}
          costUnconfiguredLogs={
            dashboardData.businessStats.costUnconfiguredLogs
          }
          t={dashboardData.t}
        />
      )}

      <StatsCards
        groupedStatsData={groupedStatsData}
        loading={dashboardData.loading}
        getTrendSpec={getTrendSpec}
        CARD_PROPS={CARD_PROPS}
        CHART_CONFIG={CHART_CONFIG}
      />

      {/* API信息和图表面板 */}
      <div className='mb-4'>
        <div
          className={`grid grid-cols-1 gap-4 ${dashboardData.hasApiInfoPanel ? 'lg:grid-cols-4' : ''}`}
        >
          <ChartsPanel
            activeChartTab={dashboardData.activeChartTab}
            setActiveChartTab={dashboardData.setActiveChartTab}
            spec_line={dashboardCharts.spec_line}
            spec_model_line={dashboardCharts.spec_model_line}
            spec_pie={dashboardCharts.spec_pie}
            spec_rank_bar={dashboardCharts.spec_rank_bar}
            spec_channel_requests_bar={dashboardCharts.spec_channel_requests_bar}
            spec_channel_quota_bar={dashboardCharts.spec_channel_quota_bar}
            spec_channel_model_bar={dashboardCharts.spec_channel_model_bar}
            spec_model_channel_bar={dashboardCharts.spec_model_channel_bar}
            channelUsageWindow={dashboardData.channelUsageWindow}
            setChannelUsageWindow={dashboardData.setChannelUsageWindow}
            onChannelUsageWindowChange={handleChannelUsageWindowChange}
            channelAnalysisTopN={dashboardData.channelAnalysisTopN}
            setChannelAnalysisTopN={dashboardData.setChannelAnalysisTopN}
            selectedAnalysisModel={dashboardData.selectedAnalysisModel}
            setSelectedAnalysisModel={dashboardData.setSelectedAnalysisModel}
            selectedAnalysisChannel={dashboardData.selectedAnalysisChannel}
            setSelectedAnalysisChannel={dashboardData.setSelectedAnalysisChannel}
            onChannelBarClick={handleChannelBarClick}
            onChannelModelBarClick={handleChannelModelBarClick}
            onModelChannelBarClick={handleModelChannelBarClick}
            modelOptions={modelOptions}
            channelOptions={channelOptions}
            channelAnalysisRows={dashboardCharts.channelAnalysisRows}
            CARD_PROPS={CARD_PROPS}
            CHART_CONFIG={CHART_CONFIG}
            FLEX_CENTER_GAP2={FLEX_CENTER_GAP2}
            hasApiInfoPanel={dashboardData.hasApiInfoPanel}
            t={dashboardData.t}
          />

          {dashboardData.hasApiInfoPanel && (
            <ApiInfoPanel
              apiInfoData={apiInfoData}
              handleCopyUrl={(url) => handleCopyUrl(url, dashboardData.t)}
              handleSpeedTest={handleSpeedTest}
              CARD_PROPS={CARD_PROPS}
              FLEX_CENTER_GAP2={FLEX_CENTER_GAP2}
              ILLUSTRATION_SIZE={ILLUSTRATION_SIZE}
              t={dashboardData.t}
            />
          )}
        </div>
      </div>

      {/* 系统公告和常见问答卡片 */}
      {dashboardData.hasInfoPanels && (
        <div className='mb-4'>
          <div className='grid grid-cols-1 lg:grid-cols-4 gap-4'>
            {/* 公告卡片 */}
            {dashboardData.announcementsEnabled && (
              <AnnouncementsPanel
                announcementData={announcementData}
                announcementLegendData={ANNOUNCEMENT_LEGEND_DATA.map(
                  (item) => ({
                    ...item,
                    label: dashboardData.t(item.label),
                  }),
                )}
                CARD_PROPS={CARD_PROPS}
                ILLUSTRATION_SIZE={ILLUSTRATION_SIZE}
                t={dashboardData.t}
              />
            )}

            {/* 常见问答卡片 */}
            {dashboardData.faqEnabled && (
              <FaqPanel
                faqData={faqData}
                CARD_PROPS={CARD_PROPS}
                FLEX_CENTER_GAP2={FLEX_CENTER_GAP2}
                ILLUSTRATION_SIZE={ILLUSTRATION_SIZE}
                t={dashboardData.t}
              />
            )}

            {/* 服务可用性卡片 */}
            {dashboardData.uptimeEnabled && (
              <UptimePanel
                uptimeData={dashboardData.uptimeData}
                uptimeLoading={dashboardData.uptimeLoading}
                activeUptimeTab={dashboardData.activeUptimeTab}
                setActiveUptimeTab={dashboardData.setActiveUptimeTab}
                loadUptimeData={dashboardData.loadUptimeData}
                uptimeLegendData={uptimeLegendData}
                renderMonitorList={(monitors) =>
                  renderMonitorList(
                    monitors,
                    (status) => getUptimeStatusColor(status, UPTIME_STATUS_MAP),
                    (status) =>
                      getUptimeStatusText(
                        status,
                        UPTIME_STATUS_MAP,
                        dashboardData.t,
                      ),
                    dashboardData.t,
                  )
                }
                CARD_PROPS={CARD_PROPS}
                ILLUSTRATION_SIZE={ILLUSTRATION_SIZE}
                t={dashboardData.t}
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default Dashboard;
