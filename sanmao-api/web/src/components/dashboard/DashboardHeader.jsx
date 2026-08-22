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
import { isAdmin } from '../../helpers';
import { Button } from '@douyinfe/semi-ui';
import { RefreshCw, Search } from 'lucide-react';

const DashboardHeader = ({
  getGreeting,
  greetingVisible,
  showSearchModal,
  refresh,
  loading,
  t,
}) => {
  return (
    <div
      className='mb-5 rounded-3xl px-5 py-5'
      style={{
        border: '1px solid var(--semi-color-border)',
        background:
          'linear-gradient(135deg, var(--semi-color-bg-1), var(--semi-color-bg-0))',
        boxShadow: '0 18px 60px var(--semi-color-shadow)',
      }}
    >
      <div className='flex items-start justify-between gap-4'>
        <div className='min-w-0'>
          <div
            className='mb-3 inline-flex items-center rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.24em]'
            style={{
              border: '1px solid var(--semi-color-primary-light-active)',
              background: 'var(--semi-color-primary-light-default)',
              color: 'var(--semi-color-primary)',
            }}
          >
            Console
          </div>
          <h2
            className='text-2xl font-semibold transition-opacity duration-1000 ease-in-out'
            style={{
              opacity: greetingVisible ? 1 : 0,
              color: 'var(--semi-color-text-0)',
            }}
          >
            {getGreeting}
          </h2>
          <p
            className='mt-2 max-w-2xl text-sm'
            style={{ color: 'var(--semi-color-text-1)' }}
          >
            {isAdmin()
              ? t('这里是统一中转运营台：查看消耗、监控渠道、管理额度，掌握经营状况。')
              : t('在这里查看你的用量、消费与剩余额度，管理你的 API 密钥。')}
          </p>
        </div>
        <div className='flex gap-3 self-start'>
          <Button
            type='tertiary'
            icon={<Search size={16} />}
            onClick={showSearchModal}
            className='!rounded-full'
            style={{
              background: 'var(--semi-color-primary)',
              color: 'var(--semi-color-white)',
            }}
          />
          <Button
            type='tertiary'
            icon={<RefreshCw size={16} />}
            onClick={refresh}
            loading={loading}
            className='!rounded-full'
            style={{
              background: 'var(--semi-color-info)',
              color: 'var(--semi-color-white)',
            }}
          />
        </div>
      </div>
    </div>
  );
};

export default DashboardHeader;
