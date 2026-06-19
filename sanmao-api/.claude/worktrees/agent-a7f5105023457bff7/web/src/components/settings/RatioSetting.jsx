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

import React, { useEffect, useState } from 'react';
import { Banner, Card, Collapse, Spin, Tabs } from '@douyinfe/semi-ui';
import { useTranslation } from 'react-i18next';

import GroupRatioSettings from '../../pages/Setting/Ratio/GroupRatioSettings';
import ModelRatioSettings from '../../pages/Setting/Ratio/ModelRatioSettings';
import ModelSettingsVisualEditor from '../../pages/Setting/Ratio/ModelSettingsVisualEditor';
import ModelRatioNotSetEditor from '../../pages/Setting/Ratio/ModelRationNotSetEditor';
import UpstreamRatioSync from '../../pages/Setting/Ratio/UpstreamRatioSync';

import { API, showError, toBoolean } from '../../helpers';

const RatioSetting = () => {
  const { t } = useTranslation();

  let [inputs, setInputs] = useState({
    ModelPrice: '',
    ModelRatio: '',
    CacheRatio: '',
    CreateCacheRatio: '',
    CompletionRatio: '',
    GroupRatio: '',
    GroupGroupRatio: '',
    ImageRatio: '',
    AudioRatio: '',
    AudioCompletionRatio: '',
    AutoGroups: '',
    DefaultUseAutoGroup: false,
    ExposeRatioEnabled: false,
    UserUsableGroups: '',
    'group_ratio_setting.group_special_usable_group': '',
  });

  const [loading, setLoading] = useState(false);

  const getOptions = async () => {
    const res = await API.get('/api/option/');
    const { success, message, data } = res.data;
    if (success) {
      let newInputs = {};
      data.forEach((item) => {
        if (item.value.startsWith('{') || item.value.startsWith('[')) {
          try {
            item.value = JSON.stringify(JSON.parse(item.value), null, 2);
          } catch (e) {
            // 如果后端返回的不是合法 JSON，直接展示
          }
        }
        if (['DefaultUseAutoGroup', 'ExposeRatioEnabled'].includes(item.key)) {
          newInputs[item.key] = toBoolean(item.value);
        } else {
          newInputs[item.key] = item.value;
        }
      });
      setInputs(newInputs);
    } else {
      showError(message);
    }
  };

  const onRefresh = async () => {
    try {
      setLoading(true);
      await getOptions();
    } catch (error) {
      showError('刷新失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    onRefresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <Spin spinning={loading} size='large'>
      {/* 模型倍率设置以及价格编辑器 */}
      <Card style={{ marginTop: '10px' }}>
        <Banner
          type='info'
          bordered
          fullMode={false}
          closeIcon={null}
          style={{ marginBottom: 16 }}
          title={t('新手建议')}
          description={
            <div>
              <div>{t('平时你只需要改“模型倍率”。')}</div>
              <div>{t('固定价格先留空；留空就按倍率卖。')}</div>
              <div>{t('只有你想给某个模型写死单价时，才去填固定价格。')}</div>
            </div>
          }
        />
        <Tabs type='card' defaultActiveKey='model'>
          <Tabs.TabPane tab={t('新手模式（推荐）')} itemKey='model'>
            <ModelRatioSettings options={inputs} refresh={onRefresh} />
          </Tabs.TabPane>
          <Tabs.TabPane tab={t('用户组折扣')} itemKey='group'>
            <GroupRatioSettings options={inputs} refresh={onRefresh} />
          </Tabs.TabPane>
        </Tabs>
        <Collapse style={{ marginTop: 16 }}>
          <Collapse.Panel
            header={t('更多设置（大多数时候不用）')}
            itemKey='advanced-pricing-tools'
          >
            <Banner
              type='warning'
              bordered
              fullMode={false}
              closeIcon={null}
              style={{ marginBottom: 16 }}
              description={t('这些入口偏专业。你如果只是想卖模型，先不用管。')}
            />
            <Tabs type='card' defaultActiveKey='visual'>
              <Tabs.TabPane tab={t('给模型写死单价')} itemKey='visual'>
                <ModelSettingsVisualEditor options={inputs} refresh={onRefresh} />
              </Tabs.TabPane>
              <Tabs.TabPane tab={t('补齐还没设置的模型')} itemKey='unset_models'>
                <ModelRatioNotSetEditor options={inputs} refresh={onRefresh} />
              </Tabs.TabPane>
              <Tabs.TabPane tab={t('从上游同步倍率')} itemKey='upstream_sync'>
                <UpstreamRatioSync options={inputs} refresh={onRefresh} />
              </Tabs.TabPane>
            </Tabs>
          </Collapse.Panel>
        </Collapse>
      </Card>
    </Spin>
  );
};

export default RatioSetting;
