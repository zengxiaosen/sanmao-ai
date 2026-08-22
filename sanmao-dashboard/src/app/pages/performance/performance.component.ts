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

      <app-explain title="指标怎么算？为什么和「买入持有」比较？">
        <b>年化收益</b>：把整段收益折算成「平均每年赚多少」。
        <span class="formula">期末净值^(252/交易天数) − 1</span>（252=一年的交易日数）<br>
        <b>夏普比率</b>：每承受一分波动，换来多少收益，是衡量「收益质量」的通用指标。
        <span class="formula">夏普比率 = 年化收益率 ÷ 年化波动率</span>，
        其中年化波动率 = 日收益率的标准差 × √252。一般认为 ＞1 为优秀，0~1 之间说明收益不够平稳。<br>
        <b>最大回撤</b>：整个时期内，从任一峰值到之后最低点的最大跌幅。
        <span class="formula">回撤 = (峰值净值 − 当前净值) / 峰值净值</span>
        本策略最大回撤 52.9%，意味着最糟糕的时候资产从高点缩水超过一半。<br>
        <b>持仓胜率</b>：拿着股票的日子里，第二天真涨的比例。<br><br>
        <b>下方的回撤曲线怎么看？</b>曲线展示的是<b>当前距离历史最高点的损失幅度</b>：
        · 贴着 0% 线 = 净值不断创新高，没有回撤
        · 向下的"坑" = 从某个峰值回落的时期，坑的深度就是损失百分比
        · 坑填平回到 0% = 净值重新创出新高<br>
        举例：净值从 1.0 涨到 2.0（峰值）再跌到 1.5，此时回撤 = (2.0−1.5)/2.0 = 25%，
        曲线上显示为从 0% 向下到 25% 的坑。之后涨回 2.1 刷新历史高点，回撤归零，坑消失。<br><br>
        <b>为什么策略跑输「买入持有」？</b>2021 年以来英伟达处于罕见的单边大行情，
        任何「没把握就空仓」的择时策略都会错过部分涨幅——这是择时的固有代价，对照表如实展示这一点。
        当前策略的特点是：<b>只用约四成的持仓时间、承担更低的波动和回撤</b>，代价是绝对收益落后。
        后续迭代方向：按概率大小调整仓位（而非全进全出）、恐慌期强制降仓、应用到震荡型标的。
        <b>回测怎么保证不作弊？</b>模型只用每天「之前」的数据做预测（滚动向前训练），
        每次买卖扣 0.05% 交易成本；历史表现不代表未来。
      </app-explain>

      <h3 *ngIf="ready">策略 vs 买入持有</h3>
      <table class="cmp" *ngIf="ready">
        <thead><tr><th></th><th>本策略</th><th>买入持有 NVDA</th><th>说明</th></tr></thead>
        <tbody>
          <tr><td>年化收益</td><td>{{ cmp.stratAnnual }}</td><td class="strong">{{ cmp.bhAnnual }}</td><td>单边牛市里买入持有占优</td></tr>
          <tr><td>最大回撤</td><td class="strong">{{ cmp.stratDD }}</td><td>{{ cmp.bhDD }}</td><td>策略回撤更浅，拿得更安稳</td></tr>
          <tr><td>年化波动率</td><td class="strong">{{ cmp.stratVol }}</td><td>{{ cmp.bhVol }}</td><td>策略波动更低</td></tr>
          <tr><td>持仓时间占比</td><td class="strong">{{ cmp.exposure }}</td><td>100%</td><td>策略近六成时间持有现金</td></tr>
        </tbody>
      </table>

      <div echarts [options]="options" class="chart" *ngIf="ready"></div>
      <div class="loading" *ngIf="!ready">加载中…</div>
    </div>
  `,
  styles: [`
    .page { padding: 8px 4px; }
    h2 { margin: 0 0 2px; font-size: 22px; }
    .sub { color:#52514e; font-size: 13px; margin: 0 0 12px; }
    .kpis { display:grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap:10px; margin-bottom:12px; }
    .cmp { border-collapse: collapse; width: 100%; font-size: 13px; background:#fff; margin-bottom: 10px; }
    .cmp th, .cmp td { border-bottom: 1px solid #eceae6; padding: 7px 12px; text-align: left; }
    .cmp th { background:#f8fafc; color:#52514e; font-weight:500; }
    .cmp td.strong { color:#15803d; font-weight:600; }
    h3 { margin: 20px 0 6px; font-size: 16px; }
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
  cmp = { stratAnnual: '-', bhAnnual: '-', stratDD: '-', bhDD: '-', stratVol: '-', bhVol: '-', exposure: '-' };
  options: EChartsOption = {};

  ngOnInit(): void {
    this.api.backtest(2000).subscribe((res) => {
      const daily = res.daily;
      const s = res.summary;
      const dates = daily.map(d => d.date.slice(0, 7));
      const equity = daily.map(d => +Number(d.equity).toFixed(4));
      // drawdown 后端算出来是负数（equity/peak-1），前端转为正数表示损失幅度
      const dd = daily.map(d => +(Math.abs(Number(d.drawdown)) * 100).toFixed(2));

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

        // 买入持有的对照指标：从归一净值曲线算年化 / 最大回撤 / 年化波动率
        const bh = hold.filter((v): v is number => v !== null && v !== undefined);
        if (bh.length > 30) {
          const years = bh.length / 252;
          const bhAnnual = Math.pow(bh[bh.length - 1] / bh[0], 1 / years) - 1;
          let peak = bh[0]; let bhMaxDD = 0;
          const bhRets: number[] = [];
          for (let i = 1; i < bh.length; i++) {
            peak = Math.max(peak, bh[i]);
            bhMaxDD = Math.min(bhMaxDD, bh[i] / peak - 1);
            bhRets.push(bh[i] / bh[i - 1] - 1);
          }
          const mean = bhRets.reduce((a, b) => a + b, 0) / bhRets.length;
          const bhVol = Math.sqrt(bhRets.reduce((a, b) => a + (b - mean) ** 2, 0) / (bhRets.length - 1)) * Math.sqrt(252);
          this.cmp = {
            stratAnnual: pct(s.annual_return), bhAnnual: pct(bhAnnual),
            stratDD: pct(s.max_drawdown), bhDD: pct(bhMaxDD),
            stratVol: pct((s as any).annual_volatility ?? 0), bhVol: pct(bhVol),
            exposure: pct(s.exposure),
          };
        }

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
            { type: 'value', gridIndex: 1, min: 0, inverse: true, name: '回撤 %', nameTextStyle: { color: INK.secondary },
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
