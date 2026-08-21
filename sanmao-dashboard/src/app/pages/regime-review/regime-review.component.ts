import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NgxEchartsDirective } from 'ngx-echarts';
import type { EChartsOption } from 'echarts';

import { ApiService } from '../../core/api.service';
import { ExplainComponent } from '../../core/explain.component';
import { REGIME_META, SEQ_BLUE, INK } from '../../core/viz-theme';
import { factorInfo } from '../../core/factor-dict';
import { ReviewResponse } from '../../core/models';

// 市场状态与复盘页（P4）——
//   1. 状态带：把每天染成四种市场状态之一（状态语义色：绿=牛、红=熊、橙=恐慌、灰=震荡）。
//   2. 状态 × 因子热力图：证明「因子有效性随市场状态切换」（课题核心论点的证据图）。
//   3. 自动复盘：管线每次跑完生成的人话结论。
@Component({
  selector: 'app-regime-review',
  standalone: true,
  imports: [CommonModule, NgxEchartsDirective, ExplainComponent],
  template: `
    <div class="page">
      <h2>市场状态与复盘</h2>
      <p class="sub">同一个因子，牛市里好用、恐慌期失灵——这页展示市场状态怎么划分、以及因子有效性怎么随状态切换。</p>

      <app-explain title="四种「市场状态」是怎么划分的？">
        每天收盘后按两条简单规则给市场贴标签（规则透明，人人可复算）：<br>
        1. <b>VIX 恐慌指数 > 25</b> → <b style="color:#ec835a">高波动</b>（无论涨跌，先算恐慌期）<br>
        2. 否则看<b>过去 60 个交易日（约3个月）的涨跌幅</b>：
        涨超 8% → <b style="color:#0ca30c">上行</b>；跌超 8% → <b style="color:#d03b3b">下行</b>；
        其余 → <b style="color:#8b8a85">震荡</b><br><br>
        下面的彩色横带就是 2018 年以来每天的状态。能明显看到：2020 年疫情（橙色恐慌）、
        2022 年加息（红橙相间）、2023-24 AI 行情（大片绿色）。
      </app-explain>

      <div class="band-legend" *ngIf="ready">
        <span *ngFor="let r of regimeLegend"><i [style.background]="r.color"></i>{{ r.short }}：{{ r.plain }}</span>
      </div>
      <div echarts [options]="regimeOptions" class="chart-regime" *ngIf="ready"></div>

      <h3>因子有效性 × 市场状态（课题核心证据图）</h3>
      <app-explain title="这张热力图怎么读？">
        <b>一行=一种市场状态，一列=一个因子</b>。颜色越深，代表这个因子在这种状态下
        「和第二天涨跌的关系」越可信（统计显著性 <span class="formula">|t| 值</span>，
        由该状态下的所有交易日回归得出）。<br><br>
        <b>怎么发现「因子失效」？</b>同一列上下颜色差异大 = 这个因子只在特定市场状态下有用。
        比如某动量因子在「上行」行深、在「高波动」行浅——恐慌期追涨杀跌就是失灵的。
        这正是本课题「自适应因子系统」要解决的问题：状态切换时，自动换用当前状态下有效的因子。
      </app-explain>
      <div echarts [options]="perfOptions" class="chart-perf" *ngIf="ready"></div>

      <h3>自动复盘（每次数据更新后自动生成）</h3>
      <div class="review" *ngIf="review">
        <div class="meta">生成于 {{ review.generated_at }} · 数据区间 {{ review.data_range?.start }} ~ {{ review.data_range?.end }} · 由规则模板生成，非 AI 自由发挥，可复现</div>
        <ul>
          <li *ngFor="let line of review.narrative">{{ line }}</li>
        </ul>
      </div>

      <div class="loading" *ngIf="!ready">加载中…</div>
    </div>
  `,
  styles: [`
    .page { padding: 8px 4px; }
    h2 { margin: 0 0 2px; font-size: 22px; }
    h3 { margin: 26px 0 6px; font-size: 16px; }
    .sub { color:#52514e; font-size: 13px; margin: 0 0 12px; }
    .band-legend { font-size:12px; color:#52514e; display:flex; flex-wrap:wrap; gap:14px; margin: 4px 0 4px; }
    .band-legend i { display:inline-block; width:10px; height:10px; border-radius:2px; margin-right:5px; }
    .chart-regime { height: 170px; width: 100%; }
    .chart-perf { height: 380px; width: 100%; }
    .review { background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:14px 18px; }
    .review .meta { color:#94a3b8; font-size:12px; margin-bottom:8px; }
    .review ul { margin:0; padding-left: 20px; }
    .review li { font-size: 14px; line-height: 2.0; color:#1f2937; }
    .loading { color:#999; padding:40px; text-align:center; }
  `],
})
export class RegimeReviewComponent implements OnInit {
  private api = inject(ApiService);
  ready = false;
  review?: ReviewResponse;
  regimeOptions: EChartsOption = {};
  perfOptions: EChartsOption = {};
  regimeLegend = Object.values(REGIME_META);

  ngOnInit(): void {
    this.api.regime().subscribe((res) => {
      const timeline = res.timeline;
      const dates = timeline.map(d => d.date.slice(0, 7));

      this.regimeOptions = {
        tooltip: {
          formatter: (p: any) => {
            const d = timeline[p.dataIndex];
            const meta = REGIME_META[d.regime];
            return `${d.regime.split(' ')[1] ?? d.regime}（${timeline[p.dataIndex].date}）<br/>` +
              `<span style="color:#8b8a85">${meta?.plain ?? ''}</span><br/>` +
              `近60日涨跌 ${(d.ret_trend * 100).toFixed(1)}% · VIX ${d.vix_level?.toFixed(1) ?? '-'}`;
          },
        },
        grid: { left: 20, right: 20, top: 6, bottom: 40 },
        xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 10, color: INK.secondary, interval: 120 }, axisTick: { show: false } },
        yAxis: { show: false, max: 1 },
        series: [{
          type: 'bar', barCategoryGap: '0%',
          data: timeline.map(d => ({ value: 1, itemStyle: { color: REGIME_META[d.regime]?.color ?? '#cbd5e1' } })),
        }],
      };

      // 状态 × 因子显著性热力图（顺序色：单蓝色系浅→深）
      const regimes: string[] = [...new Set(res.factor_performance.map(p => p.regime))];
      const factors: string[] = [...new Set(res.factor_performance.map(p => p.factor))]
        // 按平均显著性排序，最有信息量的因子排前面
        .sort((a, b) => {
          const avg = (f: string) => {
            const rows = res.factor_performance.filter(p => p.factor === f);
            return rows.reduce((s, r) => s + r.mean_abs_t, 0) / rows.length;
          };
          return avg(b) - avg(a);
        });
      const factorLabels = factors.map(f => factorInfo(f).name);
      const heat: [number, number, number][] = res.factor_performance.map(p =>
        [factors.indexOf(p.factor), regimes.indexOf(p.regime), +p.mean_abs_t.toFixed(2)]);
      const maxT = Math.max(1, ...res.factor_performance.map(p => p.mean_abs_t));

      this.perfOptions = {
        tooltip: {
          confine: true,
          formatter: (p: any) => {
            const perf = res.factor_performance.find(
              x => x.factor === factors[p.data[0]] && x.regime === regimes[p.data[1]]);
            const t = p.data[2];
            const judge = t >= 2 ? '关系很可信' : t >= 1.2 ? '有一定关系' : t >= 0.8 ? '关系较弱' : '基本无关（噪声）';
            return `<b>${factorLabels[p.data[0]]}</b> 在「${regimes[p.data[1]].split(' ')[1] ?? regimes[p.data[1]]}」时期<br/>` +
              `显著性 |t| = <b>${t}</b>（${judge}）<br/>` +
              `<span style="color:#8b8a85">基于该状态下 ${perf?.days ?? '-'} 个交易日的回归</span>`;
          },
        },
        grid: { left: 96, right: 20, top: 14, bottom: 96 },
        xAxis: { type: 'category', data: factorLabels, axisLabel: { fontSize: 11, rotate: 45, color: INK.primary }, axisTick: { show: false } },
        yAxis: { type: 'category', data: regimes.map(r => r.split(' ')[1] ?? r), axisLabel: { fontSize: 12, color: INK.primary }, axisTick: { show: false } },
        visualMap: {
          min: 0, max: maxT, calculable: true, orient: 'horizontal', left: 'center', bottom: 4,
          text: ['关系可信(深)', '无关(浅)'], textStyle: { fontSize: 11, color: INK.secondary },
          inRange: { color: [SEQ_BLUE[0], SEQ_BLUE[2], SEQ_BLUE[4], SEQ_BLUE[6]] },
        },
        series: [{
          type: 'heatmap', data: heat,
          itemStyle: { borderColor: '#fcfcfb', borderWidth: 1.5 },
          emphasis: { itemStyle: { shadowBlur: 4, shadowColor: 'rgba(0,0,0,0.25)' } },
        }],
      };
      this.ready = true;
    });

    this.api.review().subscribe((review) => (this.review = review));
  }
}
