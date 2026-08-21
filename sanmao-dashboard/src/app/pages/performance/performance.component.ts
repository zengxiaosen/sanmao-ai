import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NgxEchartsDirective } from 'ngx-echarts';
import type { EChartsOption } from 'echarts';

import { ApiService } from '../../core/api.service';
import { ExplainComponent } from '../../core/explain.component';
import { CAT, INK, STATUS } from '../../core/viz-theme';

// 回测绩效页 —— 回答「如果 2021 年起就按模型信号操作，钱会怎么变？」
//
// 设计：KPI 行（每个指标带人话注释）→ 资金曲线（含买入持有对照）→ 回撤（下格，同轴时间）。
// 双轴改为上下两格；新增「买入持有 NVDA」对照线，诚实展示策略跑输/跑赢基准。
@Component({
  selector: 'app-performance',
  standalone: true,
  imports: [CommonModule, NgxEchartsDirective, ExplainComponent],
  template: `
    <div class="page">
      <h2>回测绩效</h2>
      <p class="sub">假设从 2021 年起，每天按模型信号操作（概率≥55% 持有、否则空仓），1 元本金会变成多少。</p>

      <div class="kpis" *ngIf="ready">
        <div class="kpi" *ngFor="let k of kpis">
          <div class="k-label">{{ k.label }}</div>
          <div class="k-num" [style.color]="k.color">{{ k.value }}</div>
          <div class="k-note">{{ k.note }}</div>
        </div>
      </div>

      <app-explain title="这些指标是什么意思？回测可信吗？">
        <b>年化收益</b>：把整段收益折算成「平均每年赚多少」。
        <span class="formula">期末净值^(252/交易天数) − 1</span>（252=一年的交易日数）<br>
        <b>夏普比率</b>：每承受一分波动，换来多少收益。＜1 说明赚得比较颠簸，机构一般希望＞1。
        <span class="formula">年化收益 ÷ 年化波动率</span><br>
        <b>最大回撤</b>：期间从最高点最多跌下来多少。-44% 意味着最惨时资产缩水近一半——这是本策略目前最大的短板。<br>
        <b>持仓胜率</b>：拿着股票的日子里，第二天真涨的比例。54% 略好于抛硬币，靠「涨时在场、跌时空仓」积累优势。<br><br>
        <b>回测怎么保证不作弊？</b>模型只用每天「之前」的数据做预测（滚动向前训练），
        且每次买卖都扣了 0.05% 交易成本。但回测终究是历史演习：
        <b>历史赚钱 ≠ 未来赚钱</b>，这也是页面下方给出「买入持有」对照的原因——
        AI 行情里单纯拿住 NVDA 不动是个很强的对手。
      </app-explain>

      <div echarts [options]="options" class="chart" *ngIf="ready"></div>
      <div class="loading" *ngIf="!ready">加载中…</div>
    </div>
  `,
  styles: [`
    .page { padding: 8px 4px; }
    h2 { margin: 0 0 2px; font-size: 22px; }
    .sub { color:#52514e; font-size: 13px; margin: 0 0 12px; }
    .kpis { display:grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap:10px; margin-bottom:12px; }
    .kpi { background:#fff; border:1px solid #eceae6; border-radius:10px; padding:10px 14px; }
    .k-label { font-size:12px; color:#64748b; }
    .k-num { font-size:22px; font-weight:650; margin:2px 0; }
    .k-note { font-size:11px; color:#8b8a85; line-height:1.5; }
    .chart { height: 560px; width: 100%; }
    .loading { color:#999; padding:40px; text-align:center; }
  `],
})
export class PerformanceComponent implements OnInit {
  private api = inject(ApiService);
  ready = false;
  kpis: { label: string; value: string; note: string; color: string }[] = [];
  options: EChartsOption = {};

  ngOnInit(): void {
    this.api.backtest(2000).subscribe((res) => {
      const daily = res.daily;
      const s = res.summary;
      const dates = daily.map(d => d.date.slice(0, 7));
      const equity = daily.map(d => +Number(d.equity).toFixed(4));
      const dd = daily.map(d => +(Number(d.drawdown) * 100).toFixed(2));

      // 买入持有对照：用策略在场收益反推不出，须用价格。signals 接口有 close；
      // 这里直接用 equity 同期 close 会缺，退而求其次：由 strategy_ret 无法还原，
      // 所以从 /signals 拿全周期 close 归一。
      this.api.signals(0).subscribe((sig) => {
        const closeMap = new Map(sig.rows.map(r => [r.date, Number(r.close)]));
        const closes = daily.map(d => closeMap.get(d.date));
        let hold: (number | null)[] = [];
        const first = closes.find(c => c !== undefined);
        hold = closes.map(c => (c !== undefined && first ? +(c / first).toFixed(4) : null));

        const pct = (v: number) => (v * 100).toFixed(1) + '%';
        this.kpis = [
          { label: '年化收益', value: pct(s.annual_return), note: '平均每年赚多少', color: s.annual_return > 0 ? STATUS.good : STATUS.critical },
          { label: '夏普比率', value: s.sharpe.toFixed(2), note: '收益 ÷ 波动，>1 才算优秀', color: s.sharpe >= 1 ? STATUS.good : INK.primary },
          { label: '最大回撤', value: pct(s.max_drawdown), note: '最惨时从高点跌多少（本策略短板）', color: STATUS.critical },
          { label: '持仓胜率', value: pct(s.hit_rate_when_in_market), note: '持有的日子里次日真涨的比例', color: INK.primary },
          { label: '在场时间', value: pct(s.exposure), note: '有多大比例的日子拿着股票', color: INK.primary },
        ];

        this.options = {
          axisPointer: { link: [{ xAxisIndex: 'all' }] },
          tooltip: {
            trigger: 'axis',
            formatter: (params: any) => {
              const i = params[0].dataIndex;
              const h = hold[i];
              return `${daily[i].date}<br/>策略净值 <b>${equity[i]}</b>` +
                (h ? `<br/>买入持有净值 <b>${h}</b>` : '') +
                `<br/>当前回撤 <b>${dd[i]}%</b>`;
            },
          },
          legend: { top: 0, data: ['策略净值', '买入持有 NVDA（对照）'], textStyle: { fontSize: 12, color: INK.secondary } },
          grid: [
            { left: 64, right: 20, top: 34, height: 300 },
            { left: 64, right: 20, top: 380, height: 120 },
          ],
          xAxis: [
            { type: 'category', gridIndex: 0, data: dates, axisLabel: { show: false }, axisTick: { show: false } },
            { type: 'category', gridIndex: 1, data: dates, axisLabel: { fontSize: 10, color: INK.secondary, interval: 120 } },
          ],
          yAxis: [
            { type: 'value', gridIndex: 0, scale: true, name: '净值（起点=1）', nameTextStyle: { color: INK.secondary },
              axisLabel: { fontSize: 11, color: INK.secondary }, splitLine: { lineStyle: { color: INK.grid } } },
            { type: 'value', gridIndex: 1, max: 0, name: '回撤 %', nameTextStyle: { color: INK.secondary },
              axisLabel: { fontSize: 11, color: INK.secondary }, splitLine: { lineStyle: { color: INK.grid } } },
          ],
          series: [
            { name: '策略净值', type: 'line', xAxisIndex: 0, yAxisIndex: 0, data: equity,
              showSymbol: false, lineStyle: { width: 2.5, color: CAT.blue }, z: 3 },
            { name: '买入持有 NVDA（对照）', type: 'line', xAxisIndex: 0, yAxisIndex: 0, data: hold,
              showSymbol: false, lineStyle: { width: 1.5, color: '#c8c7c2' }, z: 2 },
            { name: '回撤', type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: dd,
              showSymbol: false, lineStyle: { width: 1.5, color: STATUS.critical },
              areaStyle: { color: 'rgba(208,59,59,0.12)' } },
          ],
        };
        this.ready = true;
      });
    });
  }
}
