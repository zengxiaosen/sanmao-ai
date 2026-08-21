import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NgxEchartsDirective } from 'ngx-echarts';
import type { EChartsOption } from 'echarts';

import { ApiService } from '../../core/api.service';
import { ExplainComponent } from '../../core/explain.component';
import { CAT, INK, STATUS } from '../../core/viz-theme';

// 交易信号页 —— 回答「模型今天怎么说？过去它说对过吗？」
//
// 设计（对照 dataviz 方法）：
//   顶部=结论卡（今天的建议，最重要的信息做成 hero，不用图）。
//   图=上下两块共享时间轴（价格一块、概率一块），替代原来的双轴图——
//   双轴图是数据可视化第一大反模式（两个刻度让人误读相关性）。
//   持有时段用价格线下方的绿色底带表达，直觉=「绿色区间里策略拿着股票」。
@Component({
  selector: 'app-signals',
  standalone: true,
  imports: [CommonModule, NgxEchartsDirective, ExplainComponent],
  template: `
    <div class="page">
      <h2>交易信号</h2>
      <p class="sub">模型每天收盘后给出「明天上涨的概率」，概率够高就持有，不够就空仓观望。</p>

      <div class="verdict" *ngIf="ready" [class.long]="isLong" [class.flat]="!isLong">
        <div class="v-main">
          <div class="v-label">今日建议（{{ latestDate }}）</div>
          <div class="v-action">{{ isLong ? '持有 📈' : '空仓观望 ⏸️' }}</div>
        </div>
        <div class="v-item">
          <div class="v-label">模型判断的明日上涨概率</div>
          <div class="v-num">{{ probPct }}%</div>
          <div class="v-note">{{ probNote }}</div>
        </div>
        <div class="v-item">
          <div class="v-label">最新收盘价</div>
          <div class="v-num">\${{ latestClose }}</div>
        </div>
      </div>

      <app-explain title="「上涨概率」是怎么算出来的？为什么 55% 才买？">
        每天收盘后，模型把当天 22 个因子的数值（涨幅、波动、公告情绪、VIX……）喂给一个
        <b>XGBoost 分类模型</b>（一种由几百棵决策树投票的机器学习算法），
        它输出一个 0~100% 的数：<span class="formula">prob_up = 模型认为「明天收盘价高于今天」的概率</span>。<br><br>
        <b>为什么 ≥55% 才持有？</b>股市短期接近抛硬币（50%），55% 是要求模型「明显比抛硬币有把握」才动手，
        低于这个线就空仓拿现金。这条线是策略参数，不是模型输出。<br>
        <b>模型是怎么训练的？</b>只用「过去三年」的数据训练，预测「下一个季度」，然后窗口往前滚——
        保证每一天的预测都只用了那天之前的信息，不偷看未来（walk-forward 回测）。
      </app-explain>

      <div echarts [options]="options" class="chart" *ngIf="ready"></div>
      <div class="loading" *ngIf="!ready">加载中…</div>
    </div>
  `,
  styles: [`
    .page { padding: 8px 4px; }
    h2 { margin: 0 0 2px; font-size: 22px; }
    .sub { color:#52514e; font-size: 13px; margin: 0 0 12px; }
    .verdict { display:flex; gap:28px; align-items:stretch; border-radius:12px; padding:16px 22px; margin-bottom:12px; }
    .verdict.long { background:#f0fdf4; border:1px solid #bbf7d0; }
    .verdict.flat { background:#f8fafc; border:1px solid #e2e8f0; }
    .v-label { font-size:12px; color:#64748b; margin-bottom:2px; }
    .v-action { font-size:30px; font-weight:700; color:#0f172a; }
    .v-num { font-size:26px; font-weight:600; color:#0f172a; }
    .v-note { font-size:12px; color:#8b8a85; }
    .v-item { border-left:1px solid #e2e8f0; padding-left:24px; }
    .chart { height: 520px; width: 100%; }
    .loading { color:#999; padding:40px; text-align:center; }
  `],
})
export class SignalsComponent implements OnInit {
  private api = inject(ApiService);
  ready = false;
  isLong = false;
  latestDate = '';
  latestClose = '';
  probPct = '';
  probNote = '';
  options: EChartsOption = {};

  ngOnInit(): void {
    this.api.signals(250).subscribe((res) => {
      const rows = res.rows;
      const dates = rows.map(r => r.date.slice(5));
      const close = rows.map(r => +Number(r.close).toFixed(2));
      const prob = rows.map(r => +(Number(r.prob_up) * 100).toFixed(1));
      const longBand = rows.map(r => ((r.position ?? (r.prob_up >= 0.55 ? 1 : 0)) > 0 ? 1 : 0));

      const latest = res.latest;
      this.isLong = (latest.position ?? 0) > 0;
      this.latestDate = latest.date;
      this.latestClose = Number(latest.close).toFixed(2);
      const p = Number(latest.prob_up) * 100;
      this.probPct = p.toFixed(1);
      this.probNote = p >= 55 ? '超过 55% 门槛 → 持有' : `未到 55% 门槛（还差 ${(55 - p).toFixed(1)} 个点）→ 空仓`;

      // 持有时段 -> markArea 区间（绿色底带）
      const areas: [{ xAxis: string }, { xAxis: string }][] = [];
      let start = -1;
      longBand.forEach((v, i) => {
        if (v === 1 && start === -1) start = i;
        if ((v === 0 || i === longBand.length - 1) && start !== -1) {
          const end = v === 1 ? i : i - 1;
          areas.push([{ xAxis: dates[start] }, { xAxis: dates[end] }]);
          start = -1;
        }
      });

      this.options = {
        // 上下两个格子共享一条时间轴（axisPointer 联动），替代双轴
        axisPointer: { link: [{ xAxisIndex: 'all' }] },
        tooltip: {
          trigger: 'axis',
          formatter: (params: any) => {
            const i = params[0].dataIndex;
            const held = longBand[i] === 1;
            return `${rows[i].date}<br/>收盘 <b>$${close[i]}</b><br/>` +
              `模型判断次日上涨概率 <b>${prob[i]}%</b><br/>` +
              `策略动作：<b>${held ? '持有' : '空仓'}</b>`;
          },
        },
        grid: [
          { left: 64, right: 20, top: 30, height: 260 },
          { left: 64, right: 20, top: 330, height: 130 },
        ],
        xAxis: [
          { type: 'category', gridIndex: 0, data: dates, axisLabel: { show: false }, axisTick: { show: false } },
          { type: 'category', gridIndex: 1, data: dates, axisLabel: { fontSize: 10, color: INK.secondary, interval: 24 } },
        ],
        yAxis: [
          { type: 'value', gridIndex: 0, scale: true, name: '股价 $', nameTextStyle: { color: INK.secondary },
            axisLabel: { fontSize: 11, color: INK.secondary }, splitLine: { lineStyle: { color: INK.grid } } },
          { type: 'value', gridIndex: 1, min: 0, max: 100, name: '上涨概率 %', nameTextStyle: { color: INK.secondary },
            axisLabel: { fontSize: 11, color: INK.secondary }, splitLine: { lineStyle: { color: INK.grid } } },
        ],
        series: [
          {
            name: '收盘价', type: 'line', xAxisIndex: 0, yAxisIndex: 0, data: close,
            showSymbol: false, lineStyle: { width: 2, color: CAT.blue },
            // 绿色底带 = 策略持有的时段
            markArea: {
              silent: true, itemStyle: { color: 'rgba(12,163,12,0.10)' },
              data: areas,
            },
          },
          {
            name: '上涨概率', type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: prob,
            showSymbol: false, lineStyle: { width: 2, color: CAT.orange },
            // 55% 门槛虚线：过线才买
            markLine: {
              silent: true, symbol: 'none',
              label: { formatter: '55% 买入门槛', position: 'insideEndTop', fontSize: 11, color: INK.secondary },
              lineStyle: { type: 'dashed', color: STATUS.warning, width: 1.5 },
              data: [{ yAxis: 55 }],
            },
          },
        ],
      };
      this.ready = true;
    });
  }
}
