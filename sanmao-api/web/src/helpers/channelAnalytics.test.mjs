import assert from 'node:assert/strict';

import { buildChannelAnalysisView } from './channelAnalytics.js';

const channelItems = [
  {
    channel_id: 1,
    channel_name: 'alpha',
    request_count: 12,
    tokens: 120,
    quota: 3.25,
  },
  {
    channel_id: 2,
    channel_name: 'beta',
    request_count: 7,
    tokens: 70,
    quota: 1.5,
  },
];

const channelModelItems = [
  {
    channel_id: 1,
    channel_name: 'alpha',
    model_name: 'gpt-4o',
    request_count: 10,
    tokens: 100,
    quota: 2.5,
  },
  {
    channel_id: 1,
    channel_name: 'alpha',
    model_name: 'claude-3-5-sonnet',
    request_count: 2,
    tokens: 20,
    quota: 0.75,
  },
  {
    channel_id: 2,
    channel_name: 'beta',
    model_name: 'gpt-4o',
    request_count: 7,
    tokens: 70,
    quota: 1.5,
  },
];

const baseView = buildChannelAnalysisView({
  channelItems,
  channelModelItems,
  selectedModel: '',
  selectedChannel: '',
  topN: 10,
});

assert.equal(baseView.channelRequestData[0].channelId, '1');
assert.equal(baseView.channelQuotaData[0].Channel, 'alpha');
assert.equal(baseView.channelModelData.length, 3);
assert.equal(baseView.modelChannelData.length, 3);
assert.deepEqual(
  baseView.detailRows.map((row) => [row.channel, row.model]),
  [
    ['alpha', 'gpt-4o'],
    ['beta', 'gpt-4o'],
    ['alpha', 'claude-3-5-sonnet'],
  ],
);

const filteredView = buildChannelAnalysisView({
  channelItems,
  channelModelItems,
  selectedModel: 'gpt-4o',
  selectedChannel: '1',
  topN: 10,
});

assert.equal(filteredView.channelModelData.length, 2);
assert.equal(filteredView.modelChannelData.length, 2);
assert.deepEqual(filteredView.detailRows.map((row) => row.channel), [
  'alpha',
  'alpha',
]);
assert.deepEqual(filteredView.detailRows.map((row) => row.model), [
  'gpt-4o',
  'claude-3-5-sonnet',
]);
