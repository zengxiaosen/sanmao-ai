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

import React, { useContext, useEffect, useState } from 'react';
import { Button, Card, Banner, Typography } from '@douyinfe/semi-ui';
import { IconGift } from '@douyinfe/semi-icons';
import { useTranslation } from 'react-i18next';
import { API, showError, showInfo, renderQuota } from '../../helpers';
import { UserContext } from '../../context/User';

const { Title, Text } = Typography;

const Redeem = () => {
  const { t } = useTranslation();
  const [userState, userDispatch] = useContext(UserContext);
  const [code, setCode] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [lastAdded, setLastAdded] = useState(null);

  const refreshSelf = async () => {
    try {
      const res = await API.get('/api/user/self');
      if (res.data.success) {
        userDispatch({ type: 'login', payload: res.data.data });
      }
    } catch (e) {
      // 静默失败，余额展示用本地缓存兜底
    }
  };

  useEffect(() => {
    refreshSelf();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const balanceQuota = Number(userState?.user?.quota || 0);

  const redeem = async () => {
    const key = code.trim();
    if (key === '') {
      showInfo(t('请输入兑换码！'));
      return;
    }
    setSubmitting(true);
    try {
      const res = await API.post('/api/user/topup', { key });
      const { success, message, data } = res.data;
      if (success) {
        setLastAdded(data);
        setCode('');
        if (userState.user) {
          userDispatch({
            type: 'login',
            payload: {
              ...userState.user,
              quota: (userState.user.quota || 0) + data,
            },
          });
        }
      } else {
        showError(message);
      }
    } catch (err) {
      showError(t('请求失败'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className='mx-auto w-full max-w-2xl px-4 pb-6 sm:px-6 mt-[60px] pt-6'>
      <div className='mb-5'>
        <Title heading={3} style={{ margin: 0 }}>
          {t('兑换')}
        </Title>
        <Text type='tertiary'>{t('输入兑换码以充值余额')}</Text>
      </div>

      {/* 当前余额卡片 */}
      <Card
        className='mb-5 overflow-hidden !rounded-2xl border-0'
        bodyStyle={{
          padding: 28,
          textAlign: 'center',
          background:
            'linear-gradient(135deg, #f97316 0%, #ea580c 60%, #c2410c 100%)',
        }}
      >
        <div style={{ color: 'rgba(255,255,255,0.9)', fontSize: 14 }}>
          {t('当前余额')}
        </div>
        <div
          style={{
            color: '#fff',
            fontSize: 40,
            fontWeight: 700,
            lineHeight: 1.2,
            marginTop: 6,
          }}
        >
          {renderQuota(balanceQuota)}
        </div>
      </Card>

      {/* 兑换码输入卡片 */}
      <Card className='mb-5 !rounded-2xl'>
        <div className='mb-2 text-sm font-medium'>{t('兑换码')}</div>
        <div className='flex flex-col gap-3'>
          <div
            className='flex items-center rounded-xl px-3'
            style={{
              border: '1px solid var(--semi-color-border)',
              height: 48,
            }}
          >
            <IconGift style={{ color: 'var(--semi-color-text-2)' }} />
            <input
              value={code}
              onChange={(e) => setCode(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') redeem();
              }}
              placeholder={t('请输入兑换码')}
              style={{
                flex: 1,
                border: 'none',
                outline: 'none',
                background: 'transparent',
                fontSize: 15,
                marginLeft: 8,
                color: 'var(--semi-color-text-0)',
              }}
            />
          </div>
          <Text type='tertiary' size='small'>
            {t('兑换码区分大小写')}
          </Text>
          <Button
            theme='solid'
            size='large'
            block
            loading={submitting}
            onClick={redeem}
            icon={<IconGift />}
            className='!rounded-xl'
          >
            {t('兑换')}
          </Button>
        </div>
      </Card>

      {lastAdded != null && (
        <Banner
          type='success'
          className='mb-5 !rounded-xl'
          closeIcon={null}
          description={
            <div>
              <div style={{ fontWeight: 600 }}>{t('兑换成功！')}</div>
              <div>
                {t('已添加：')} {renderQuota(lastAdded)}
              </div>
            </div>
          }
        />
      )}

      {/* 关于兑换码 */}
      <Card className='!rounded-2xl'>
        <div className='mb-2 text-sm font-medium'>{t('关于兑换码')}</div>
        <ul
          style={{
            margin: 0,
            paddingLeft: 18,
            color: 'var(--semi-color-text-2)',
            fontSize: 13,
            lineHeight: 1.9,
          }}
        >
          <li>{t('每个兑换码只能使用一次')}</li>
          <li>{t('兑换码可以增加余额')}</li>
          <li>{t('如有兑换问题，请联系客服')}</li>
          <li>{t('余额即时更新')}</li>
        </ul>
      </Card>
    </div>
  );
};

export default Redeem;
