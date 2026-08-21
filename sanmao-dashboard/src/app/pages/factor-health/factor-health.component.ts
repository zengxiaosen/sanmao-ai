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
      <p class="sub">模型不是黑盒：这页告诉你它当前最依赖什么因子、哪些因子正在失灵、失灵了拿什么替换。</p>

      <app-explain title="「因子体检」的三个判断是怎么做出来的？">
        对每个因子做两项检查，像体检的两个化验指标：<br>
        <b>1. 模型还看重它吗？</b>每个训练窗口结束后，读出模型内部给每个因子的权重
        （<span class="formula">feature importance，全部因子合计=1</span>）。
        把窗口按时间排开，就能看到权重的走势——持续下行说明模型在「冷落」它。<br>
        <b>2. 它和涨跌还有关系吗？</b>用最近 60 天数据做回归：因子高的日子，之后是不是真的更容易涨？
        关系的可信度用统计学的 <span class="formula">|t| 值</span> 衡量（大于 2 算很可信，小于 1 基本是噪声）。<br><br>
        两项结合定状态：<b>健康</b>（关系可信）→ <b>衰退中</b>（权重下滑或可信度走低）→
        <b>已失效</b>（权重大幅下滑且关系消失）。<br>
        <b>数据稀疏</b>是诚实声明：公告类因子一年只有十几个非零样本，统计上判断不了好坏，
        我们直接说「判断不了」，而不是硬给结论。
      </app-explain>

      <div class="chips" *ngIf="ready">
        <span class="chip ok">健康 {{ counts.active }}</span>
        <span class="chip warn">衰退中 {{ counts.decaying }}</span>
        <span class="chip bad">已失效 {{ counts.failed }}</span>
        <span class="chip na" *ngIf="counts.sparse">数据稀疏（不判定）{{ counts.sparse }}</span>
      </div>

      <h3>模型的「注意力」怎么变：因子重要性走势（前 6 名）</h3>
      <div echarts [options]="importanceOptions" class="chart" *ngIf="ready"></div>

      <h3>逐因子体检报告</h3>
      <table class="tbl" *ngIf="ready">
        <thead>
          <tr><th style="width:150px">因子</th><th style="width:110px">体检结果</th><th>判断依据（人话）</th></tr>
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
        <h3>自动替换建议（自适应因子系统的核心动作）</h3>
        <div class="rep" *ngFor="let rep of replacements">
          <span class="bad-text">{{ nameOf(rep.failed_factor) }}</span> 正在走弱
          → 建议改用同类里最健康的 <span class="ok-text">{{ rep.replacement ? nameOf(rep.replacement) : '（暂无健康同类）' }}</span>
          <span class="grp">（{{ rep.group === 'price_volume' ? '量价类' : rep.group === 'sentiment' ? '舆情类' : rep.group === 'macro' ? '宏观类' : rep.group }}内替换，逻辑可解释）</span>
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

  statusLabel(status: string): string {
    return ({ active: '✅ 健康', decaying: '⚠️ 衰退中', failed: '❌ 已失效', sparse: 'ℹ️ 数据稀疏' } as any)[status] ?? status;
  }

  whyOf(row: DecayRow & { coverage?: number }): string {
    const cov = (row as any).coverage;
    if (row.status === 'sparse') {
      return `只有 ${((cov ?? 0) * 100).toFixed(1)}% 的日子有非零取值（公告不是天天有），样本太少，统计上无法判断有效性——不下结论。`;
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
