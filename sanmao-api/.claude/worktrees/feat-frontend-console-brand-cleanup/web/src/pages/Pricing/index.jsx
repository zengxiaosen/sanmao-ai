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
import ModelPricingPage from '../../components/table/model-pricing/layout/PricingPage';

const Pricing = () => (
  <div className='bg-[radial-gradient(circle_at_top,rgba(16,185,129,0.12),transparent_28%),linear-gradient(180deg,rgba(15,23,42,0.03),transparent_18%)]'>
    <div className='mx-auto max-w-7xl px-4 pt-6 pb-3'>
      <div className='rounded-3xl border border-white/8 bg-[linear-gradient(135deg,rgba(15,23,42,0.92),rgba(17,24,39,0.94))] px-6 py-6 shadow-[0_18px_60px_rgba(2,6,23,0.20)]'>
        <div className='inline-flex items-center rounded-full border border-emerald-400/30 bg-emerald-400/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.24em] text-emerald-300'>
          Sanmao Market
        </div>
        <h1 className='mt-4 text-3xl font-semibold tracking-tight text-white'>
          模型市场与调用价格
        </h1>
        <p className='mt-3 max-w-3xl text-sm leading-7 text-slate-300'>
          这里展示当前已启用、可对外调用的模型。列表来自后台可用渠道能力和模型展示配置；如果模型只存在于渠道里但没有启用能力，或模型展示状态被关闭，就不会出现在这里。
        </p>
        <p className='mt-2 max-w-3xl text-sm leading-7 text-slate-300'>
          输入价格指用户发给模型的 tokens，输出价格指模型回复产生的 tokens。缓存读取、缓存创建、图片输入、音频输入这些价格只在对应能力实际发生时参与扣费。
        </p>
      </div>
    </div>
    <ModelPricingPage />
  </div>
);

export default Pricing;
