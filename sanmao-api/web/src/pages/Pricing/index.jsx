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
  <div className='bg-[radial-gradient(circle_at_top,rgba(245, 158, 11,0.12),transparent_28%),linear-gradient(180deg,rgba(15,23,42,0.03),transparent_18%)]'>
    <div className='mx-auto max-w-7xl px-4 pt-6 pb-3'>
      <div className='rounded-3xl border border-white/8 bg-[linear-gradient(135deg,rgba(15,23,42,0.92),rgba(17,24,39,0.94))] px-6 py-6 shadow-[0_18px_60px_rgba(2,6,23,0.20)]'>
        <div className='inline-flex items-center rounded-full border border-amber-400/30 bg-amber-400/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.24em] text-amber-300'>
          Pricing
        </div>
        <h1 className='mt-4 text-3xl font-semibold tracking-tight text-white'>
          模型与价格
        </h1>
        <p className='mt-3 text-sm leading-relaxed text-slate-400'>
          当前对外开放的模型与调用价格，按量计费。
        </p>
      </div>
    </div>
    <ModelPricingPage />
  </div>
);

export default Pricing;
