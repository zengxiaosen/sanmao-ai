import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

// explain-box —— 「这张图怎么看」统一说明框。
// 每张图上方放一个，用通俗语言说：看什么、颜色/线代表什么、数字怎么算出来的。
// 折叠式：默认收起一行，点开看完整说明，不打扰熟悉的用户。
// 文案红线：对外产品页面，不出现“小白/AI/模板生成”等字眼。
@Component({
  selector: 'app-explain',
  standalone: true,
  imports: [CommonModule],
  template: `
    <details class="explain">
      <summary>{{ title }}</summary>
      <div class="body"><ng-content></ng-content></div>
    </details>
  `,
  styles: [`
    .explain { background:#f6f8ff; border:1px solid #dbe4ff; border-radius:10px;
               padding:8px 14px; margin: 6px 0 12px; font-size:13px; }
    .explain summary { cursor:pointer; color:#3b5bcc; font-weight:500; user-select:none; }
    .explain summary::marker { color:#93a6e8; }
    .explain .body { color:#3f4756; line-height:1.9; padding:8px 2px 4px; }
    .explain .body ::ng-deep b { color:#1f2937; }
    .explain .body ::ng-deep .formula {
      display:inline-block; background:#eef2ff; border-radius:6px; padding:1px 8px;
      font-family: ui-monospace, monospace; font-size:12px; color:#3730a3; }
  `],
})
export class ExplainComponent {
  @Input() title = '图表说明';
}
