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

import React, { useEffect, useMemo, useState } from 'react';
import {
  Banner,
  Button,
  Form,
  Input,
  InputNumber,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from '@douyinfe/semi-ui';
import { IconDelete, IconPlus, IconRefresh } from '@douyinfe/semi-icons';
import { useTranslation } from 'react-i18next';
import { API, showError, showSuccess, showWarning } from '../../../helpers';
import { CHANNEL_OPTIONS } from '../../../constants';

const { Text } = Typography;

const EMPTY_CONFIG = { channels: {}, fixed_costs: [] };
const VISION_CREDIT_USD = 150 / 35000 / 7.3;
const VISION_MODEL_POINTS = {
  'gpt-5.4': [2.5, 20],
  'gpt-5.5': [3, 24],
  'gpt-5.4-mini': [0.5, 4],
  'claude-sonnet-4-6': [3, 15],
  'claude-opus-4-6': [5, 25],
  'claude-opus-4-7': [5, 25],
  'claude-opus-4-5-20251101': [5, 25],
  'claude-haiku-4-5-20251001': [1, 5],
};

function parseCostConfig(raw) {
  if (!raw || String(raw).trim() === '') return EMPTY_CONFIG;
  try {
    const parsed = JSON.parse(raw);
    return {
      channels: parsed?.channels && typeof parsed.channels === 'object' ? parsed.channels : {},
      fixed_costs: Array.isArray(parsed?.fixed_costs) ? parsed.fixed_costs : [],
    };
  } catch {
    return EMPTY_CONFIG;
  }
}

function makeRowId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function configToRows(config) {
  const rows = [];
  Object.entries(config.channels || {}).forEach(([channelId, channelConfig]) => {
    if (channelConfig?.default) {
      rows.push({
        id: makeRowId(),
        channel_id: Number(channelId),
        model_name: '',
        input_per_million: Number(channelConfig.default.input_per_million || 0),
        output_per_million: Number(channelConfig.default.output_per_million || 0),
      });
    }
    Object.entries(channelConfig?.models || {}).forEach(([modelName, modelConfig]) => {
      rows.push({
        id: makeRowId(),
        channel_id: Number(channelId),
        model_name: modelName,
        input_per_million: Number(modelConfig.input_per_million || 0),
        output_per_million: Number(modelConfig.output_per_million || 0),
      });
    });
  });
  return rows;
}

function rowsToConfig(rows) {
  const config = { channels: {}, fixed_costs: [] };
  rows.forEach((row) => {
    const channelId = String(row.channel_id || '').trim();
    if (!channelId) return;
    if (!config.channels[channelId]) {
      config.channels[channelId] = { models: {} };
    }
    const cost = {
      input_per_million: Number(row.input_per_million || 0),
      output_per_million: Number(row.output_per_million || 0),
    };
    const modelName = String(row.model_name || '').trim();
    if (modelName) {
      config.channels[channelId].models[modelName] = cost;
    } else {
      config.channels[channelId].default = cost;
    }
  });

  Object.values(config.channels).forEach((channelConfig) => {
    if (Object.keys(channelConfig.models || {}).length === 0) {
      delete channelConfig.models;
    }
  });
  return config;
}

function fixedCostsToRows(config) {
  return (config.fixed_costs || []).map((item) => ({
    id: makeRowId(),
    name: item.name || '',
    amount: Number(item.amount || 0),
    currency: item.currency || 'CNY',
    period: item.period || 'month',
    channel_ids: Array.isArray(item.channel_ids) ? item.channel_ids.map(Number) : [],
  }));
}

function mergeConfig(rows, fixedCostRows) {
  const config = rowsToConfig(rows);
  const fixedCosts = fixedCostRows
    .filter((row) => Number(row.amount || 0) > 0)
    .map((row) => ({
      name: String(row.name || '').trim() || '固定成本',
      amount: Number(row.amount || 0),
      currency: row.currency || 'CNY',
      period: row.period || 'month',
      channel_ids: Array.isArray(row.channel_ids) ? row.channel_ids.map(Number) : [],
    }));
  if (fixedCosts.length > 0) {
    config.fixed_costs = fixedCosts;
  }
  return config;
}

function formatConfig(config) {
  return JSON.stringify(config, null, 2);
}

function getChannelLabel(channelId) {
  const matched = CHANNEL_OPTIONS.find((item) => Number(item.value) === Number(channelId));
  return matched ? `${matched.label} (#${channelId})` : `渠道 #${channelId}`;
}

export default function SettingsBusinessCost(props) {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [rows, setRows] = useState([]);
  const [fixedCostRows, setFixedCostRows] = useState([]);
  const [savedConfigText, setSavedConfigText] = useState(formatConfig(EMPTY_CONFIG));
  const [channels, setChannels] = useState([]);

  const channelOptions = useMemo(() => {
    const fromChannels = channels.map((channel) => ({
      value: Number(channel.id),
      label: `${channel.name || getChannelLabel(channel.id)} (#${channel.id})`,
    }));
    const fromConstants = CHANNEL_OPTIONS.map((item) => ({
      value: Number(item.value),
      label: `${item.label} (#${item.value})`,
    }));
    const seen = new Set();
    return [...fromChannels, ...fromConstants].filter((item) => {
      if (seen.has(item.value)) return false;
      seen.add(item.value);
      return true;
    });
  }, [channels]);

  const currentConfigText = useMemo(
    () => formatConfig(mergeConfig(rows, fixedCostRows)),
    [rows, fixedCostRows],
  );
  const hasChanged = currentConfigText !== savedConfigText;

  const updateRow = (rowId, patch) => {
    setRows((prev) => prev.map((row) => (row.id === rowId ? { ...row, ...patch } : row)));
  };

  const updateFixedCostRow = (rowId, patch) => {
    setFixedCostRows((prev) => prev.map((row) => (row.id === rowId ? { ...row, ...patch } : row)));
  };

  const addDefaultRow = () => {
    setRows((prev) => [
      ...prev,
      {
        id: makeRowId(),
        channel_id: channelOptions[0]?.value || 1,
        model_name: '',
        input_per_million: 0,
        output_per_million: 0,
      },
    ]);
  };

  const addModelRow = () => {
    setRows((prev) => [
      ...prev,
      {
        id: makeRowId(),
        channel_id: channelOptions[0]?.value || 1,
        model_name: 'gpt-5.5',
        input_per_million: 0,
        output_per_million: 0,
      },
    ]);
  };

  const removeRow = (rowId) => {
    setRows((prev) => prev.filter((row) => row.id !== rowId));
  };

  const addFixedCostRow = () => {
    setFixedCostRows((prev) => [
      ...prev,
      {
        id: makeRowId(),
        name: '阿里云 Token Plan 团队版',
        amount: 0,
        currency: 'CNY',
        period: 'month',
        channel_ids: [],
      },
    ]);
  };

  const removeFixedCostRow = (rowId) => {
    setFixedCostRows((prev) => prev.filter((row) => row.id !== rowId));
  };

  const loadChannels = async () => {
    try {
      const res = await API.get('/api/channel/?p=1&page_size=1000&id_sort=true');
      if (res.data?.success) {
        const items = res.data?.data?.items || [];
        setChannels(items);
        return items;
      }
    } catch (err) {
      console.error(err);
    }
    return [];
  };

  const addRowsFromExistingChannels = async () => {
    const loadedChannels = channels.length > 0 ? channels : await loadChannels();
    setRows((prev) => {
      const existingDefaults = new Set(
        prev
          .filter((row) => !String(row.model_name || '').trim())
          .map((row) => Number(row.channel_id)),
      );
      const additions = loadedChannels
        .filter((channel) => !existingDefaults.has(Number(channel.id)))
        .map((channel) => ({
          id: makeRowId(),
          channel_id: Number(channel.id),
          model_name: '',
          input_per_million: 0,
          output_per_million: 0,
        }));
      if (additions.length === 0) {
        showWarning(t('没有可补充的渠道默认成本行'));
        return prev;
      }
      return [...prev, ...additions];
    });
  };

  const addVisionCoderCosts = () => {
    setRows((prev) => {
      const existing = new Set(
        prev.map((row) => `${row.channel_id}:${String(row.model_name || '').trim()}`),
      );
      const additions = [];
      Object.entries(VISION_MODEL_POINTS).forEach(([modelName, [inputPoints, outputPoints]]) => {
        [
          { channelId: 1, enabled: modelName.startsWith('gpt-') || modelName === 'codex-auto-review' },
          { channelId: 3, enabled: modelName.startsWith('claude-') },
        ].forEach(({ channelId, enabled }) => {
          const key = `${channelId}:${modelName}`;
          if (!enabled || existing.has(key)) return;
          additions.push({
            id: makeRowId(),
            channel_id: channelId,
            model_name: modelName,
            input_per_million: Number((inputPoints * VISION_CREDIT_USD).toFixed(9)),
            output_per_million: Number((outputPoints * VISION_CREDIT_USD).toFixed(9)),
          });
        });
      });
      if (additions.length === 0) {
        showWarning(t('VisionCoder 已没有可补充的公开价格行'));
        return prev;
      }
      return [...prev, ...additions];
    });
  };

  const onSubmit = async () => {
    if (!hasChanged) {
      showWarning(t('你似乎并没有修改什么'));
      return;
    }
    const duplicateKeys = new Set();
    const seen = new Set();
    for (const row of rows) {
      if (!row.channel_id) {
        showError(t('请先选择渠道'));
        return;
      }
      if (Number(row.input_per_million) < 0 || Number(row.output_per_million) < 0) {
        showError(t('上游成本不能小于 0'));
        return;
      }
      const key = `${row.channel_id}:${String(row.model_name || '').trim()}`;
      if (seen.has(key)) duplicateKeys.add(key);
      seen.add(key);
    }
    for (const row of fixedCostRows) {
      if (Number(row.amount || 0) < 0) {
        showError(t('固定成本不能小于 0'));
        return;
      }
    }
    if (duplicateKeys.size > 0) {
      showError(t('存在重复的渠道/模型成本行，请合并后再保存'));
      return;
    }

    setLoading(true);
    try {
      const res = await API.put('/api/option/', {
        key: 'BusinessCostConfig',
        value: currentConfigText,
      });
      if (!res.data?.success) {
        showError(res.data?.message || t('保存失败，请重试'));
        return;
      }
      setSavedConfigText(currentConfigText);
      showSuccess(t('保存成功'));
      props.refresh();
    } catch (err) {
      showError(t('保存失败，请重试'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const parsed = parseCostConfig(props.options?.BusinessCostConfig);
    const configText = formatConfig(parsed);
    setRows(configToRows(parsed));
    setFixedCostRows(fixedCostsToRows(parsed));
    setSavedConfigText(configText);
  }, [props.options?.BusinessCostConfig]);

  useEffect(() => {
    loadChannels();
  }, []);

  const columns = [
    {
      title: t('渠道'),
      dataIndex: 'channel_id',
      width: 260,
      render: (_, record) => (
        <Select
          filter
          style={{ width: '100%' }}
          optionList={channelOptions}
          value={record.channel_id}
          onChange={(value) => updateRow(record.id, { channel_id: Number(value) })}
        />
      ),
    },
    {
      title: t('模型'),
      dataIndex: 'model_name',
      render: (_, record) => (
        <Input
          value={record.model_name}
          placeholder={t('留空 = 这个渠道的默认成本')}
          onChange={(value) => updateRow(record.id, { model_name: value })}
        />
      ),
    },
    {
      title: t('输入成本'),
      dataIndex: 'input_per_million',
      width: 170,
      render: (_, record) => (
        <InputNumber
          min={0}
          step={0.01}
          precision={6}
          value={record.input_per_million}
          suffix='$/1M'
          onChange={(value) => updateRow(record.id, { input_per_million: Number(value || 0) })}
        />
      ),
    },
    {
      title: t('输出成本'),
      dataIndex: 'output_per_million',
      width: 170,
      render: (_, record) => (
        <InputNumber
          min={0}
          step={0.01}
          precision={6}
          value={record.output_per_million}
          suffix='$/1M'
          onChange={(value) => updateRow(record.id, { output_per_million: Number(value || 0) })}
        />
      ),
    },
    {
      title: t('含义'),
      width: 140,
      render: (_, record) => (
        <Tag color={record.model_name ? 'blue' : 'green'}>
          {record.model_name ? t('模型特殊成本') : t('渠道默认成本')}
        </Tag>
      ),
    },
    {
      title: t('操作'),
      width: 90,
      render: (_, record) => (
        <Popconfirm
          title={t('确认删除这条成本配置？')}
          onConfirm={() => removeRow(record.id)}
        >
          <Button icon={<IconDelete />} type='danger' theme='borderless' />
        </Popconfirm>
      ),
    },
  ];

  const fixedCostColumns = [
    {
      title: t('成本名称'),
      dataIndex: 'name',
      render: (_, record) => (
        <Input
          value={record.name}
          placeholder={t('例如：阿里云 Token Plan 团队版')}
          onChange={(value) => updateFixedCostRow(record.id, { name: value })}
        />
      ),
    },
    {
      title: t('金额'),
      dataIndex: 'amount',
      width: 150,
      render: (_, record) => (
        <InputNumber
          min={0}
          step={1}
          precision={2}
          value={record.amount}
          onChange={(value) => updateFixedCostRow(record.id, { amount: Number(value || 0) })}
        />
      ),
    },
    {
      title: t('币种'),
      dataIndex: 'currency',
      width: 120,
      render: (_, record) => (
        <Select
          style={{ width: '100%' }}
          value={record.currency}
          optionList={[
            { value: 'CNY', label: 'CNY/RMB' },
            { value: 'USD', label: 'USD' },
          ]}
          onChange={(value) => updateFixedCostRow(record.id, { currency: value })}
        />
      ),
    },
    {
      title: t('周期'),
      dataIndex: 'period',
      width: 130,
      render: (_, record) => (
        <Select
          style={{ width: '100%' }}
          value={record.period}
          optionList={[
            { value: 'month', label: t('每月') },
            { value: 'day', label: t('每天') },
            { value: 'year', label: t('每年') },
          ]}
          onChange={(value) => updateFixedCostRow(record.id, { period: value })}
        />
      ),
    },
    {
      title: t('绑定渠道'),
      dataIndex: 'channel_ids',
      render: (_, record) => (
        <Select
          multiple
          filter
          style={{ width: '100%' }}
          placeholder={t('留空 = 计入全部经营成本')}
          optionList={channelOptions}
          value={record.channel_ids}
          onChange={(value) => updateFixedCostRow(record.id, { channel_ids: value || [] })}
        />
      ),
    },
    {
      title: t('操作'),
      width: 90,
      render: (_, record) => (
        <Popconfirm
          title={t('确认删除这条固定成本？')}
          onConfirm={() => removeFixedCostRow(record.id)}
        >
          <Button icon={<IconDelete />} type='danger' theme='borderless' />
        </Popconfirm>
      ),
    },
  ];

  return (
    <Form style={{ marginBottom: 15 }}>
      <Form.Section text={t('经营成本配置')}>
        <Banner
          type='info'
          closeIcon={null}
          fullMode={false}
          description={
            <div>
              <Text>
                {t('这里填的是你购买上游 API 的真实成本，不是卖给用户的价格。看板会按：毛收入 - 上游成本 = 净利润/差价 来计算。')}
              </Text>
              <br />
              <Text type='tertiary'>
                {t('按量成本单位是美元 / 100万 Tokens。固定成本适合阿里云 Token Plan、包月套餐、服务器月租等，会按筛选时间自动折算。')}
              </Text>
            </div>
          }
        />
        <Space wrap style={{ margin: '14px 0' }}>
          <Button icon={<IconPlus />} onClick={addDefaultRow}>
            {t('添加渠道默认成本')}
          </Button>
          <Button icon={<IconPlus />} onClick={addModelRow}>
            {t('添加模型特殊成本')}
          </Button>
          <Button icon={<IconRefresh />} onClick={addRowsFromExistingChannels}>
            {t('从现有渠道生成默认行')}
          </Button>
          <Button onClick={addVisionCoderCosts}>
            {t('按 ¥150/35000 积分导入 VisionCoder')}
          </Button>
        </Space>
        <Text strong>{t('按量成本：适合 VisionCoder 这种按积分/token 扣费')}</Text>
        <Table
          rowKey='id'
          columns={columns}
          dataSource={rows}
          pagination={false}
          size='small'
          empty='暂未配置上游成本，经营看板只能显示毛收入，不能准确显示净利润。'
        />
        <div style={{ marginTop: 18 }}>
          <Space wrap style={{ marginBottom: 12 }}>
            <Text strong>{t('固定成本：适合阿里云 Token Plan 团队版、包月套餐')}</Text>
            <Button icon={<IconPlus />} onClick={addFixedCostRow}>
              {t('添加固定成本')}
            </Button>
          </Space>
          <Table
            rowKey='id'
            columns={fixedCostColumns}
            dataSource={fixedCostRows}
            pagination={false}
            size='small'
            empty='暂未配置固定成本。'
          />
        </div>
        <div style={{ marginTop: 14, display: 'flex', justifyContent: 'space-between', gap: 12 }}>
          <Text type={hasChanged ? 'warning' : 'tertiary'}>
            {hasChanged
              ? t('有未保存的成本配置，保存后看板才会按新成本计算净利润。')
              : t('成本配置已保存。')}
          </Text>
          <Button theme='solid' type='primary' loading={loading} onClick={onSubmit}>
            {t('保存经营成本配置')}
          </Button>
        </div>
      </Form.Section>
    </Form>
  );
}
