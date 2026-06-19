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

const normalizeChannelName = (item) => item.channel_name || `#${item.channel_id}`;
const formatQuota = (quota, digits = 4) => {
  const value = Number(quota || 0);
  return Number.isFinite(value) ? Number(value.toFixed(digits)) : 0;
};

export const buildChannelAnalysisView = ({
  channelItems = [],
  channelModelItems = [],
  selectedModel = '',
  selectedChannel = '',
  topN = 10,
}) => {
  const channelRequestData = channelItems
    .map((item) => ({
      channelId: String(item.channel_id),
      Channel: normalizeChannelName(item),
      Count: item.request_count || 0,
      Tokens: item.tokens || 0,
      rawQuota: item.quota || 0,
    }))
    .sort((a, b) => b.Count - a.Count)
    .slice(0, topN);

  const channelQuotaData = channelItems
    .map((item) => ({
      channelId: String(item.channel_id),
      Channel: normalizeChannelName(item),
      Count: item.request_count || 0,
      Tokens: item.tokens || 0,
      rawQuota: item.quota || 0,
      Quota: item.quota ? formatQuota(item.quota, 4) : 0,
    }))
    .sort((a, b) => b.rawQuota - a.rawQuota)
    .slice(0, topN);

  const channelModelData = channelModelItems
    .filter((item) =>
      selectedChannel ? String(item.channel_id) === String(selectedChannel) : true,
    )
    .map((item) => ({
      channelId: String(item.channel_id),
      Label: item.model_name,
      Channel: normalizeChannelName(item),
      Model: item.model_name,
      Count: item.request_count || 0,
      Tokens: item.tokens || 0,
      rawQuota: item.quota || 0,
      Quota: item.quota ? formatQuota(item.quota, 4) : 0,
    }))
    .sort((a, b) => b.rawQuota - a.rawQuota)
    .slice(0, topN);

  const modelChannelData = channelModelItems
    .filter((item) => (selectedModel ? item.model_name === selectedModel : true))
    .map((item) => ({
      channelId: String(item.channel_id),
      Label: normalizeChannelName(item),
      Channel: normalizeChannelName(item),
      Model: item.model_name,
      Count: item.request_count || 0,
      Tokens: item.tokens || 0,
      rawQuota: item.quota || 0,
      Quota: item.quota ? formatQuota(item.quota, 4) : 0,
    }))
    .sort((a, b) => b.rawQuota - a.rawQuota)
    .slice(0, topN);

  const detailSource = selectedChannel ? channelModelData : selectedModel ? modelChannelData : channelModelData;
  const detailRows = detailSource.map((item, index) => ({
    key: `${item.channelId}-${item.Model}-${index}`,
    rank: index + 1,
    channelId: item.channelId,
    channel: item.Channel,
    model: item.Model,
    count: item.Count,
    quota: item.rawQuota,
    tokens: item.Tokens || 0,
  }));

  return {
    channelRequestData,
    channelQuotaData,
    channelModelData,
    modelChannelData,
    detailRows,
    totalRequests: channelItems.reduce(
      (sum, item) => sum + (item.request_count || 0),
      0,
    ),
    totalQuota: channelItems.reduce((sum, item) => sum + (item.quota || 0), 0),
  };
};
