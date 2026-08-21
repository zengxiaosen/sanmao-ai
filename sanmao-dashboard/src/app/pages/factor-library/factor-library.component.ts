import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NgxEchartsDirective } from 'ngx-echarts';
import type { EChartsOption } from 'echarts';

import { ApiService } from '../../core/api.service';
import { ExplainComponent } from '../../core/explain.component';
import { factorInfo } from '../../core/factor-dict';
import { DIV, INK } from '../../core/viz-theme';

// 因子库页 —— 回答「模型每天看的 22 个指标是什么、现在各自什么状态」。
//
// 设计（对照 dataviz 方法）：
//   形式=热力图（网格型强弱对比的标准形式）；颜色=发散色（蓝↔灰↔红，中点必须中性）。
//   小白改造：
//     1. 因子全部用中文名，悬停显示「含义 + 计算公式 + 当日原值」。
//     2. 按大类分区（量价/舆情/宏观），行间留白分隔。
//     3. 事件类因子（大多数日子=0，热力图上全是空白）单独抽出来做「事件时间轴」，
//        不再混在热力图里假装有数据。
//     4. 点任意因子行，下方出现这因子的完整小白卡片。
@Component({
  selector: 'app-factor-library',
  standalone: true,
  imports: [CommonModule, NgxEchartsDirective, ExplainComponent],
  template: `
    <div class="page">
      <h2>因子库</h2>
      <p class="sub">模型做预测前，每天要看的 22 个指标（因子）。这页告诉你它们是什么、最近什么状态。</p>

      <app-explain title="「因子」是什么？这张图怎么看？">
        <b>因子 = 模型每天观察的一个指标</b>，好比体检表上的一项。本策略的因子分三类：<br>
        · <b>量价</b>：只看这只股票自己的价格和成交量（涨了多少、波动大不大、放量没有）<br>
        · <b>舆情</b>：看这家公司的官方公告（SEC 财报/重大事件），判断利好还是利空<br>
        · <b>宏观</b>：看整个市场的大环境（恐慌指数 VIX、美债利率、美元强弱）<br><br>
        下面的色块图：<b>一行=一个因子，一列=一天</b>。
        <span class="formula">红=当天这个因子处于自己历史上的偏高位，蓝=偏低位，灰白=正常</span>。
        比如「异常成交量」一格发红 = 那天放量了。颜色只表示「相对自己平时的高低」，不直接表示涨跌好坏。<br>
        <b>鼠标悬停任何色块</b>可以看：这个因子的含义、计算公式、当天的实际数值。
      </app-explain>

      <div echarts [options]="heatOptions" [style.height.px]="heatHeight" class="chart" *ngIf="ready"></div>

      <h3>事件类因子（不放热力图的原因：大多数日子没有事件）</h3>
      <app-explain title="为什么这几个因子单独展示？">
        「财报事件数」「利润承压信号」这类因子来自公司公告，而公告不是天天有——
        NVDA 一年只发十几次公告，所以这些因子 <b>99% 的日子取值为 0</b>。
        放进热力图会是一大片空白，还会被误读成「因子失效」。
        这里改用<b>事件时间轴</b>：只标出真的发生了事件的日子。
      </app-explain>
      <div echarts [options]="eventOptions" class="chart-events" *ngIf="ready && hasEvents"></div>
      <p class="empty" *ngIf="ready && !hasEvents">最近 {{ days }} 天没有公告事件。</p>

      <h3>因子说明书（点击上图任意行也会跳到这里）</h3>
      <div class="dict">
        <div class="dict-group" *ngFor="let g of dictGroups">
          <div class="dict-title">{{ g.name }}</div>
          <table class="tbl">
            <thead><tr><th style="width:120px">因子</th><th>它衡量什么</th><th>怎么算</th><th style="width:90px">最新值</th></tr></thead>
            <tbody>
              <tr *ngFor="let f of g.items" [id]="'dict-' + f.key" [class.hl]="f.key === highlightKey">
                <td><b>{{ f.name }}</b><div class="key">{{ f.key }}</div></td>
                <td>{{ f.meaning }}</td>
                <td class="calc">{{ f.calc }}</td>
                <td class="mono">{{ f.latest }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="loading" *ngIf="!ready">加载中…</div>
    </div>
  `,
  styles: [`
    .page { padding: 8px 4px; }
    h2 { margin: 0 0 2px; font-size: 22px; }
    h3 { margin: 26px 0 4px; font-size: 16px; }
    .sub { color:#52514e; font-size: 13px; margin: 0 0 12px; }
    .chart { width: 100%; }
    .chart-events { width: 100%; height: 180px; }
    .empty { color:#8b8a85; font-size:13px; padding: 8px 0; }
    .dict-group { margin-bottom: 18px; }
    .dict-title { font-weight: 600; font-size: 14px; color:#1f2937; margin: 10px 0 6px; }
    .tbl { border-collapse: collapse; width: 100%; font-size: 13px; background:#fff; }
    .tbl th, .tbl td { border-bottom: 1px solid #eceae6; padding: 7px 10px; text-align: left; vertical-align: top; }
    .tbl th { background:#f8fafc; color:#52514e; font-weight:500; }
    .tbl tr.hl { background:#fef9c3; }
    .key { color:#8b8a85; font-family: ui-monospace, monospace; font-size: 11px; }
    .calc { color:#52514e; }
    .mono { font-family: ui-monospace, monospace; }
    .loading { color:#999; padding:40px; text-align:center; }
  `],
})
export class FactorLibraryComponent implements OnInit {
  private api = inject(ApiService);
  ready = false;
  hasEvents = false;
  days = 40;
  heatHeight = 480;
  highlightKey = '';
  heatOptions: EChartsOption = {};
  eventOptions: EChartsOption = {};
  dictGroups: { name: string; items: { key: string; name: string; meaning: string; calc: string; latest: string }[] }[] = [];

  ngOnInit(): void {
    this.api.factors(this.days).subscribe((res) => {
      // 事件类因子（覆盖稀疏）单独走时间轴；其余进热力图。
      const isSparse = (row: { values: number[] }) => {
        const nonzero = row.values.filter(v => Math.abs(v) > 1e-9).length;
        return nonzero / row.values.length < 0.1;
      };
      const denseRows = res.matrix.filter(r => !isSparse(r));
      const sparseRows = res.matrix.filter(r => isSparse(r));
      const dates = res.dates;
      const shortDates = dates.map(d => d.slice(5)); // 只显示 月-日

      // ---- 热力图（按大类排序，行内附中文名）----
      const groupOrder = ['量价', '舆情', '宏观'];
      const sorted = [...denseRows].sort((a, b) => {
        const ga = groupOrder.indexOf(factorInfo(a.factor).group);
        const gb = groupOrder.indexOf(factorInfo(b.factor).group);
        return ga - gb || a.factor.localeCompare(b.factor);
      });
      const yLabels = sorted.map(r => {
        const info = factorInfo(r.factor);
        return `${info.name}`;
      });
      const heat: [number, number, number][] = [];
      sorted.forEach((row, y) => row.values.forEach((v, x) => heat.push([x, y, +v.toFixed(2)])));
      this.heatHeight = 60 + sorted.length * 24;

      this.heatOptions = {
        tooltip: {
          confine: true,
          formatter: (p: any) => {
            const row = sorted[p.data[1]];
            const info = factorInfo(row.factor);
            const z = p.data[2];
            const state = z > 1 ? '明显偏高' : z > 0.3 ? '略偏高' : z < -1 ? '明显偏低' : z < -0.3 ? '略偏低' : '正常范围';
            return `<b>${info.name}</b>（${info.group}）<br/>` +
              `${dates[p.data[0]]}：<b>${state}</b>（相对强度 ${z > 0 ? '+' : ''}${z}）<br/>` +
              `<span style="color:#8b8a85">含义：${info.meaning}<br/>算法：${info.calc}<br/>最新原值：${row.latest}</span>`;
          },
        },
        grid: { left: 110, right: 14, top: 8, bottom: 46 },
        xAxis: { type: 'category', data: shortDates, axisLabel: { fontSize: 10, color: INK.secondary, interval: 4 }, axisTick: { show: false } },
        yAxis: { type: 'category', data: yLabels, axisLabel: { fontSize: 12, color: INK.primary }, axisTick: { show: false },
                 triggerEvent: true },
        visualMap: {
          min: -2.5, max: 2.5, calculable: true, orient: 'horizontal', left: 'center', bottom: 0,
          text: ['偏高(红)', '偏低(蓝)'], textStyle: { fontSize: 11, color: INK.secondary },
          // 发散色：蓝 ↔ 中性灰 ↔ 红（中点必须中性，才能读出「正常」）
          inRange: { color: [DIV.neg, DIV.mid, DIV.pos] },
        },
        series: [{
          type: 'heatmap', data: heat,
          itemStyle: { borderColor: '#fcfcfb', borderWidth: 1.5 },  // 2px 表面间隔规则
          emphasis: { itemStyle: { shadowBlur: 4, shadowColor: 'rgba(0,0,0,0.25)' } },
        }],
      };

      // ---- 事件时间轴（散点：只画非零事件日）----
      const eventPoints: { name: string; data: [string, number][] }[] = [];
      sparseRows.forEach((row) => {
        const pts: [string, number][] = [];
        row.values.forEach((v, x) => { if (Math.abs(v) > 1e-9) pts.push([shortDates[x], 1]); });
        if (pts.length) eventPoints.push({ name: factorInfo(row.factor).name, data: pts });
      });
      this.hasEvents = eventPoints.length > 0;
      if (this.hasEvents) {
        const eventNames = eventPoints.map(e => e.name);
        this.eventOptions = {
          tooltip: { formatter: (p: any) => `${p.seriesName}<br/>${p.data[0]} 有事件` },
          grid: { left: 110, right: 14, top: 8, bottom: 30 },
          xAxis: { type: 'category', data: shortDates, axisLabel: { fontSize: 10, color: INK.secondary, interval: 4 } },
          yAxis: { type: 'category', data: eventNames, axisLabel: { fontSize: 12, color: INK.primary } },
          series: eventPoints.map((e, i) => ({
            name: e.name, type: 'scatter', symbolSize: 12,
            data: e.data.map(([d]) => [d, e.name]),
            itemStyle: { color: '#2a78d6' },
          })),
        };
      }

      // ---- 因子说明书 ----
      const byGroup = new Map<string, { key: string; name: string; meaning: string; calc: string; latest: string }[]>();
      res.matrix.forEach((row) => {
        const info = factorInfo(row.factor);
        const item = {
          key: row.factor, name: info.name, meaning: info.meaning, calc: info.calc,
          latest: this.fmt(row.latest),
        };
        byGroup.set(info.group, [...(byGroup.get(info.group) ?? []), item]);
      });
      this.dictGroups = groupOrder.filter(g => byGroup.has(g)).map(g => ({ name: this.groupTitle(g), items: byGroup.get(g)! }));

      this.ready = true;
    });
  }

  private groupTitle(g: string): string {
    return { '量价': '量价因子（看股票自己）', '舆情': '舆情因子（看公司公告，来源 SEC 官网）', '宏观': '宏观因子（看大环境，来源美联储 FRED）' }[g] ?? g;
  }

  private fmt(v: number): string {
    if (v === 0) return '0';
    if (Math.abs(v) >= 100) return v.toFixed(1);
    if (Math.abs(v) >= 1) return v.toFixed(2);
    return v.toFixed(4);
  }
}
