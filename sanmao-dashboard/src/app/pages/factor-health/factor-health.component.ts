import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NgxEchartsDirective } from 'ngx-echarts';
import type { EChartsOption } from 'echarts';

import { ApiService } from '../../core/api.service';
import { ExplainComponent } from '../../core/explain.component';
import { CAT_ORDER, INK } from '../../core/viz-theme';
import { factorInfo } from '../../core/factor-dict';
import { DecayRow, ReplacementRow } from '../../core/models';

// 因子体检页（P3 核心）—— 回答「模型现在靠哪些因子吃饭？哪些因子不灵了？」
//
// 相比上一版的改进：
//   1. 新增 sparse（数据稀疏）状态——事件类因子样本太少，不妄下衰退结论（诚实性修复）。
//   2. 因子全部用中文名；每个判断给出「为什么」。
//   3. 重要性曲线只画 top6 并直接标注末端（direct label），颜色用校验过的分类色。
@Component({
  selector: 'app-factor-health',
  standalone: true,
  imports: [CommonModule, NgxEchartsDirective, ExplainComponent],
  template: `
    <div class="page">
      <h2>因子体检</h2>
      <p class="sub">这页展示模型当前最依赖哪些因子、哪些因子正在失灵、失灵后用什么替换。</p>

      <app-explain title="「模型权重」「体检结论」是怎么算出来的？">
        <b>什么是「模型给因子的权重」？</b>预测模型是几百棵决策树的投票组合，训练完成后可以统计出：
        做判断时每个因子被用到的贡献占比，全部因子加起来 = 100%。
        比如「当日公告数」权重 7.9%，意思是模型的判断里约 7.9% 的贡献来自这个因子——
        权重高 = 模型当前最信赖它。<br><br>
        <b>权重会变吗？怎么变？</b>会。模型每个季度用「最近三年」的数据重新训练一次，
        市场风格变了，重训后的权重就会跟着变。下面的曲线图就是把历年每次重训的权重连起来：
        2022 年加息期，利率类因子的权重明显抬升；2023 年 AI 行情启动后，动量类因子权重上行。
        <b>曲线持续下行 = 模型正在冷落这个因子</b>，这就是「因子衰退」的第一个信号。<br><br>
        <b>第二个信号：它和涨跌还有关系吗？</b>用最近 60 个交易日做回归——
        每天记下（因子值 x，次日涨跌 y），拟合直线 <span class="formula">y ≈ α + β·x</span>，
        再算斜率的可信度 <span class="formula">|t| = β ÷ β的估计误差</span>。
        举例：|t| = 2.1 表示这个关系大概率是真的；|t| = 0.4 表示散点乱成一团，关系基本是巧合。<br><br>
        <b>体检结论规则（两个信号同时看）：</b><br>
        · 权重下滑超 2 个百分点 <b>且</b> |t| &lt; 0.6 → <b>已失效</b><br>
        · 权重下滑超 1 个百分点 <b>且</b> |t| &lt; 1.0 → <b>衰退中</b><br>
        · 其余 → <b>健康</b><br>
        · 公告类因子一年只有十几个非零样本，回归结果没有统计意义 → 标为<b>样本不足</b>，不评级。
      </app-explain>

      <div class="chips" *ngIf="ready">
        <span class="chip ok">健康 {{ counts.active }}</span>
        <span class="chip warn">衰退中 {{ counts.decaying }}</span>
        <span class="chip bad">已失效 {{ counts.failed }}</span>
        <span class="chip na" *ngIf="counts.sparse">样本不足（不评级）{{ counts.sparse }}</span>
      </div>

      <h3>模型的「注意力」怎么变：因子重要性走势（前 6 名）</h3>
      <div echarts [options]="importanceOptions" class="chart" *ngIf="ready"></div>

      <h3>逐因子体检报告</h3>
      <table class="tbl" *ngIf="ready">
        <thead>
          <tr><th style="width:150px">因子</th><th style="width:110px">体检结果</th><th>判断依据</th></tr>
        </thead>
        <tbody>
          <tr *ngFor="let row of decay">
            <td><b>{{ nameOf(row.factor) }}</b><div class="key">{{ row.factor }}</div></td>
            <td><span class="badge" [class]="'badge ' + row.status">{{ statusLabel(row.status) }}</span></td>
            <td class="why">{{ whyOf(row) }}</td>
          </tr>
        </tbody>
      </table>

      <ng-container *ngIf="replacements.length">
        <h3>自动替换建议</h3>
        <app-explain title="「同类」指什么？为什么只在同类里替换？">
          22 个因子分三大类，替换只在同一类内进行，保证换上去的因子和换下来的看的是同一类信息：<br>
          · <b>量价类</b>（8 个）：1日涨幅、5日涨幅、20日涨幅、20日波动率、偏离10日均线、偏离50日均线、日内振幅、异常成交量<br>
          · <b>舆情类</b>（9 个）：当日公告数、公告平均情绪、公告加权情绪、公告最高置信度、财报事件数、宏观事件数、利润承压信号、指引疲软信号、供应链风险信号<br>
          · <b>宏观类</b>（5 个）：VIX恐慌指数、VIX 5日变化、10年美债利率、利率5日变化、美元5日变化<br><br>
          规则：某因子被判「衰退/失效」时，从它的同类中选当前权重最高的健康因子作为替代。
          若同类中暂时没有健康因子（例如宏观类 5 个全在衰退），则显示「暂无健康同类」，等待下次重训再评估。
        </app-explain>
        <div class="rep" *ngFor="let rep of replacements">
          <span class="bad-text">{{ nameOf(rep.failed_factor) }}</span> 正在走弱
          → 建议改用同类里最健康的 <span class="ok-text">{{ rep.replacement ? nameOf(rep.replacement) : '（暂无健康同类）' }}</span>
          <span class="grp">（{{ groupCn(rep.group) }}内替换）</span>
        </div>
      </ng-container>

      <div class="loading" *ngIf="!ready">加载中…</div>
    </div>
  `,
  styles: [`
    .page { padding: 8px 4px; }
    h2 { margin: 0 0 2px; font-size: 22px; }
    h3 { margin: 24px 0 6px; font-size: 16px; }
    .sub { color:#52514e; font-size: 13px; margin: 0 0 12px; }
    .chips { margin: 4px 0 8px; }
    .chip { display:inline-block; border-radius:12px; padding:4px 12px; margin-right:8px; font-size:13px; }
    .chip.ok { background:#dcfce7; color:#166534; }
    .chip.warn { background:#fef9c3; color:#854d0e; }
    .chip.bad { background:#fee2e2; color:#991b1b; }
    .chip.na { background:#f1f5f9; color:#475569; }
    .chart { height: 340px; width: 100%; }
    .tbl { border-collapse: collapse; width: 100%; font-size: 13px; background:#fff; }
    .tbl th, .tbl td { border-bottom: 1px solid #eceae6; padding: 7px 10px; text-align: left; vertical-align: top; }
    .tbl th { background:#f8fafc; color:#52514e; font-weight:500; }
    .key { color:#8b8a85; font-family: ui-monospace, monospace; font-size: 11px; }
    .why { color:#3f4756; line-height: 1.7; }
    .badge { border-radius:10px; padding:2px 10px; font-size:12px; white-space:nowrap; }
    .badge.active { background:#dcfce7; color:#166534; }
    .badge.decaying { background:#fef9c3; color:#854d0e; }
    .badge.failed { background:#fee2e2; color:#991b1b; }
    .badge.sparse { background:#f1f5f9; color:#475569; }
    .rep { font-size: 13px; padding: 5px 0; }
    .bad-text { color:#b91c1c; font-weight:600; }
    .ok-text { color:#15803d; font-weight:600; }
    .grp { color:#8b8a85; }
    .loading { color:#999; padding:40px; text-align:center; }
  `],
})
export class FactorHealthComponent implements OnInit {
  private api = inject(ApiService);
  ready = false;
  counts = { active: 0, decaying: 0, failed: 0, sparse: 0 };
  decay: DecayRow[] = [];
  replacements: ReplacementRow[] = [];
  importanceOptions: EChartsOption = {};

  nameOf(key: string): string { return factorInfo(key).name; }

  groupCn(group: string): string {
    return ({ price_volume: '量价类', sentiment: '舆情类', macro: '宏观类' } as any)[group] ?? group;
  }

  statusLabel(status: string): string {
    return ({ active: '✅ 健康', decaying: '⚠️ 衰退中', failed: '❌ 已失效', sparse: 'ℹ️ 样本不足' } as any)[status] ?? status;
  }

  whyOf(row: DecayRow & { coverage?: number }): string {
    const cov = (row as any).coverage;
    if (row.status === 'sparse') {
      return `该因子来自公司公告，而公告不是每天都有：只有 ${((cov ?? 0) * 100).toFixed(1)}% 的交易日有非零取值，样本量不足以做统计判断，故不评级。`;
    }
    const t = row.recent_abs_t;
    const tText = t >= 2 ? `和涨跌的关系很可信（|t|=${t.toFixed(1)}）`
      : t >= 1.2 ? `和涨跌仍有关系（|t|=${t.toFixed(1)}）`
      : t >= 0.8 ? `和涨跌的关系变弱（|t|=${t.toFixed(1)}，1 以下接近噪声）`
      : `和涨跌几乎无关了（|t|=${t.toFixed(1)}）`;
    const trend = row.importance_trend;
    const trendText = trend < -0.01 ? `模型给它的权重在下滑（${(trend * 100).toFixed(1)} 个百分点）`
      : trend > 0.01 ? `模型给它的权重在上升（+${(trend * 100).toFixed(1)} 个百分点）`
      : '模型给它的权重基本稳定';
    return `${trendText}；${tText}。`;
  }

  ngOnInit(): void {
    this.api.factorAnalytics().subscribe((res) => {
      const order: Record<string, number> = { failed: 0, decaying: 1, active: 2, sparse: 3 };
      this.decay = [...res.decay].sort((a, b) => (order[a.status] - order[b.status]) || b.recent_abs_t - a.recent_abs_t);
      this.counts = {
        active: res.decay.filter(d => d.status === 'active').length,
        decaying: res.decay.filter(d => d.status === 'decaying').length,
        failed: res.decay.filter(d => d.status === 'failed').length,
        sparse: res.decay.filter(d => d.status === 'sparse').length,
      };
      this.replacements = res.replacements;

      const windows = [...new Set(res.importance_timeline.map(p => p.window_end))].sort();
      const lastWindow = windows[windows.length - 1];
      const topFactors = res.importance_timeline
        .filter(p => p.window_end === lastWindow)
        .sort((a, b) => b.importance - a.importance)
        .slice(0, 6)
        .map(p => p.factor);

      const series = topFactors.map((factor, i) => ({
        name: factorInfo(factor).name,
        type: 'line' as const,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2, color: CAT_ORDER[i] },
        itemStyle: { color: CAT_ORDER[i] },
        // 末端直接标注（direct label）：最后一个点显示系列名
        endLabel: { show: true, formatter: '{a}', fontSize: 11, color: CAT_ORDER[i] },
        labelLayout: { moveOverlap: 'shiftY' as const },
        data: windows.map(w =>
          res.importance_timeline.find(p => p.window_end === w && p.factor === factor)?.importance ?? null),
      }));

      this.importanceOptions = {
        tooltip: {
          trigger: 'axis',
          valueFormatter: (v: any) => (v == null ? '-' : (v * 100).toFixed(1) + '%'),
        },
        legend: { top: 0, textStyle: { fontSize: 11, color: INK.secondary } },
        grid: { left: 56, right: 110, top: 34, bottom: 40 },
        xAxis: { type: 'category', data: windows, axisLabel: { fontSize: 10, color: INK.secondary } },
        yAxis: {
          type: 'value', name: '模型权重占比', nameTextStyle: { color: INK.secondary },
          axisLabel: { fontSize: 10, color: INK.secondary, formatter: (v: number) => (v * 100).toFixed(0) + '%' },
          splitLine: { lineStyle: { color: INK.grid } },
        },
        series,
      };
      this.ready = true;
    });
  }
}
