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

import React, { useEffect, useState, useRef } from 'react';
import {
  Banner,
  Button,
  Collapse,
  Col,
  Form,
  Popconfirm,
  Row,
  Space,
  Spin,
} from '@douyinfe/semi-ui';
import {
  compareObjects,
  API,
  showError,
  showSuccess,
  showWarning,
  verifyJSON,
} from '../../../helpers';
import { useTranslation } from 'react-i18next';
import { useEnabledChannelModels } from '../../../hooks/common/useEnabledChannelModels';

const FILTERED_OPTION_KEYS = [
  'ModelPrice',
  'ModelRatio',
  'CacheRatio',
  'CreateCacheRatio',
  'CompletionRatio',
  'ImageRatio',
  'AudioRatio',
  'AudioCompletionRatio',
];

const parseOptionJSON = (rawValue) => {
  if (!rawValue || rawValue.trim() === '') {
    return {};
  }
  try {
    const parsed = JSON.parse(rawValue);
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch (error) {
    return {};
  }
};

const stringifyOptionJSON = (value) => JSON.stringify(value, null, 2);

const filterOptionByModels = (rawValue, enabledModelSet) => {
  const parsed = parseOptionJSON(rawValue);
  const filtered = Object.fromEntries(
    Object.entries(parsed).filter(([model]) => enabledModelSet.has(model)),
  );
  return stringifyOptionJSON(filtered);
};

const mergeOptionByModels = (visibleRawValue, originalRawValue, enabledModelSet) => {
  const original = parseOptionJSON(originalRawValue);
  const visible = parseOptionJSON(visibleRawValue);
  const merged = { ...original };

  Object.keys(merged).forEach((model) => {
    if (enabledModelSet.has(model)) {
      delete merged[model];
    }
  });

  Object.entries(visible).forEach(([model, value]) => {
    merged[model] = value;
  });

  return stringifyOptionJSON(merged);
};

export default function ModelRatioSettings(props) {
  const [loading, setLoading] = useState(false);
  const [inputs, setInputs] = useState({
    ModelPrice: '',
    ModelRatio: '',
    CacheRatio: '',
    CreateCacheRatio: '',
    CompletionRatio: '',
    ImageRatio: '',
    AudioRatio: '',
    AudioCompletionRatio: '',
    ExposeRatioEnabled: false,
  });
  const refForm = useRef();
  const [inputsRow, setInputsRow] = useState(inputs);
  const { t } = useTranslation();
  const { enabledModels } = useEnabledChannelModels(t);

  async function onSubmit() {
    try {
      await refForm.current
        .validate()
        .then(() => {
          const enabledModelSet = new Set(enabledModels);
          const submitInputs = { ...inputs };
          const submitBaseline = { ...inputsRow };

          FILTERED_OPTION_KEYS.forEach((key) => {
            submitInputs[key] = mergeOptionByModels(
              inputs[key],
              props.options[key],
              enabledModelSet,
            );
            submitBaseline[key] = props.options[key] || '';
          });

          const updateArray = compareObjects(submitBaseline, submitInputs);
          if (!updateArray.length)
            return showWarning(t('你似乎并没有修改什么'));

          const requestQueue = updateArray.map((item) => {
            const value =
              typeof submitInputs[item.key] === 'boolean'
                ? String(submitInputs[item.key])
                : submitInputs[item.key];
            return API.put('/api/option/', { key: item.key, value });
          });

          setLoading(true);
          Promise.all(requestQueue)
            .then((res) => {
              if (res.includes(undefined)) {
                return showError(
                  requestQueue.length > 1
                    ? t('部分保存失败，请重试')
                    : t('保存失败'),
                );
              }

              for (let i = 0; i < res.length; i++) {
                if (!res[i].data.success) {
                  return showError(res[i].data.message);
                }
              }

              showSuccess(t('保存成功'));
              props.refresh();
            })
            .catch((error) => {
              console.error('Unexpected error:', error);
              showError(t('保存失败，请重试'));
            })
            .finally(() => {
              setLoading(false);
            });
        })
        .catch(() => {
          showError(t('请检查输入'));
        });
    } catch (error) {
      showError(t('请检查输入'));
      console.error(error);
    }
  }

  async function resetModelRatio() {
    try {
      let res = await API.post(`/api/option/rest_model_ratio`);
      if (res.data.success) {
        showSuccess(res.data.message);
        props.refresh();
      } else {
        showError(res.data.message);
      }
    } catch (error) {
      showError(error);
    }
  }

  useEffect(() => {
    const currentInputs = {};
    const enabledModelSet = new Set(enabledModels);
    for (let key in props.options) {
      if (Object.keys(inputs).includes(key)) {
        currentInputs[key] = FILTERED_OPTION_KEYS.includes(key)
          ? filterOptionByModels(props.options[key], enabledModelSet)
          : props.options[key];
      }
    }
    setInputs(currentInputs);
    setInputsRow(structuredClone(currentInputs));
    refForm.current.setValues(currentInputs);
  }, [enabledModels, props.options]);

  return (
    <Spin spinning={loading}>
      <Form
        values={inputs}
        getFormApi={(formAPI) => (refForm.current = formAPI)}
        style={{ marginBottom: 15 }}
      >
        <Banner
          type='info'
          bordered
          fullMode={false}
          closeIcon={null}
          style={{ marginBottom: 16 }}
          title={t('倍率怎么调')}
          description={
            <div>
              <div>{t('倍率调大，你卖得更贵，单次更赚钱。')}</div>
              <div>{t('倍率调小，你卖得更便宜，更容易吸引人来用。')}</div>
              <div>{t('大多数时候，你只需要改“模型倍率”和“输出倍率”。')}</div>
            </div>
          }
        />
        <Row gutter={16}>
          <Col xs={24} sm={16}>
            <Form.TextArea
              label={t('模型倍率')}
              extraText={t('这是最常用的入口。你主要就在这里调每个模型卖多少钱。')}
              placeholder={t('直接照着这个格式填，例如：{"gpt-5.4": 7.5, "gpt-5-codex": 5.5}')}
              field={'ModelRatio'}
              autosize={{ minRows: 6, maxRows: 12 }}
              trigger='blur'
              stopValidateWithError
              rules={[
                {
                  validator: (rule, value) => verifyJSON(value),
                  message: '不是合法的 JSON 字符串',
                },
              ]}
              onChange={(value) => setInputs({ ...inputs, ModelRatio: value })}
            />
          </Col>
        </Row>
        <Row gutter={16}>
          <Col xs={24} sm={16}>
            <Form.TextArea
              label={t('输出倍率')}
              extraText={t('这项就是生成内容怎么收费。一般 Claude 和 Codex 都建议配上。')}
              placeholder={t('直接照着这个格式填，例如：{"gpt-5.4": 6, "gpt-5-codex": 8}')}
              field={'CompletionRatio'}
              autosize={{ minRows: 6, maxRows: 12 }}
              trigger='blur'
              stopValidateWithError
              rules={[
                {
                  validator: (rule, value) => verifyJSON(value),
                  message: '不是合法的 JSON 字符串',
                },
              ]}
              onChange={(value) =>
                setInputs({ ...inputs, CompletionRatio: value })
              }
            />
          </Col>
        </Row>
        <Collapse>
          <Collapse.Panel header={t('更多倍率设置（通常不用改）')} itemKey='advanced-ratio'>
            <Row gutter={16}>
              <Col xs={24} sm={16}>
                <Form.TextArea
                  label={t('模型固定价格')}
                  extraText={t('填了这里，就按固定价格收费；留空时才按倍率收费。固定价格优先。')}
                  placeholder={t('直接照着这个格式填，例如：{"gpt-5.4": 0.2}')}
                  field={'ModelPrice'}
                  autosize={{ minRows: 6, maxRows: 12 }}
                  trigger='blur'
                  stopValidateWithError
                  rules={[
                    {
                      validator: (rule, value) => verifyJSON(value),
                      message: '不是合法的 JSON 字符串',
                    },
                  ]}
                  onChange={(value) => setInputs({ ...inputs, ModelPrice: value })}
                />
              </Col>
            </Row>
            <Row gutter={16}>
              <Col xs={24} sm={16}>
                <Form.TextArea
                  label={t('提示缓存倍率')}
                  extraText={t('只有你明确在做缓存计费时才需要改。')}
                  placeholder={t('直接照着这个格式填')}
                  field={'CacheRatio'}
                  autosize={{ minRows: 6, maxRows: 12 }}
                  trigger='blur'
                  stopValidateWithError
                  rules={[
                    {
                      validator: (rule, value) => verifyJSON(value),
                      message: '不是合法的 JSON 字符串',
                    },
                  ]}
                  onChange={(value) => setInputs({ ...inputs, CacheRatio: value })}
                />
              </Col>
            </Row>
            <Row gutter={16}>
              <Col xs={24} sm={16}>
                <Form.TextArea
                  label={t('缓存创建倍率')}
                  extraText={t('只有你明确在做缓存计费时才需要改。')}
                  placeholder={t('直接照着这个格式填')}
                  field={'CreateCacheRatio'}
                  autosize={{ minRows: 6, maxRows: 12 }}
                  trigger='blur'
                  stopValidateWithError
                  rules={[
                    {
                      validator: (rule, value) => verifyJSON(value),
                      message: '不是合法的 JSON 字符串',
                    },
                  ]}
                  onChange={(value) =>
                    setInputs({ ...inputs, CreateCacheRatio: value })
                  }
                />
              </Col>
            </Row>
            <Row gutter={16}>
              <Col xs={24} sm={16}>
                <Form.TextArea
                  label={t('图片输入倍率（仅部分模型支持该计费）')}
                  extraText={t('只有你卖图片模型时才需要改。')}
                  placeholder={t('直接照着这个格式填，例如：{"gpt-image-1": 2}')}
                  field={'ImageRatio'}
                  autosize={{ minRows: 6, maxRows: 12 }}
                  trigger='blur'
                  stopValidateWithError
                  rules={[
                    {
                      validator: (rule, value) => verifyJSON(value),
                      message: '不是合法的 JSON 字符串',
                    },
                  ]}
                  onChange={(value) => setInputs({ ...inputs, ImageRatio: value })}
                />
              </Col>
            </Row>
            <Row gutter={16}>
              <Col xs={24} sm={16}>
                <Form.TextArea
                  label={t('音频倍率（仅部分模型支持该计费）')}
                  extraText={t('只有你卖音频模型时才需要改。')}
                  placeholder={t('直接照着这个格式填，例如：{"gpt-4o-audio-preview": 16}')}
                  field={'AudioRatio'}
                  autosize={{ minRows: 6, maxRows: 12 }}
                  trigger='blur'
                  stopValidateWithError
                  rules={[
                    {
                      validator: (rule, value) => verifyJSON(value),
                      message: '不是合法的 JSON 字符串',
                    },
                  ]}
                  onChange={(value) => setInputs({ ...inputs, AudioRatio: value })}
                />
              </Col>
            </Row>
            <Row gutter={16}>
              <Col xs={24} sm={16}>
                <Form.TextArea
                  label={t('音频补全倍率（仅部分模型支持该计费）')}
                  extraText={t('只有你卖音频模型时才需要改。')}
                  placeholder={t('直接照着这个格式填，例如：{"gpt-4o-realtime": 2}')}
                  field={'AudioCompletionRatio'}
                  autosize={{ minRows: 6, maxRows: 12 }}
                  trigger='blur'
                  stopValidateWithError
                  rules={[
                    {
                      validator: (rule, value) => verifyJSON(value),
                      message: '不是合法的 JSON 字符串',
                    },
                  ]}
                  onChange={(value) =>
                    setInputs({ ...inputs, AudioCompletionRatio: value })
                  }
                />
              </Col>
            </Row>
            <Row gutter={16}>
              <Col span={16}>
                <Form.Switch
                  label={t('暴露倍率接口')}
                  field={'ExposeRatioEnabled'}
                  onChange={(value) =>
                    setInputs({ ...inputs, ExposeRatioEnabled: value })
                  }
                />
              </Col>
            </Row>
          </Collapse.Panel>
        </Collapse>
      </Form>
      <Space>
        <Button onClick={onSubmit}>{t('保存倍率设置')}</Button>
        <Popconfirm
          title={t('确定重置模型倍率吗？')}
          content={t('此修改将不可逆')}
          okType={'danger'}
          position={'top'}
          onConfirm={resetModelRatio}
        >
          <Button type={'danger'}>{t('重置模型倍率')}</Button>
        </Popconfirm>
      </Space>
    </Spin>
  );
}
