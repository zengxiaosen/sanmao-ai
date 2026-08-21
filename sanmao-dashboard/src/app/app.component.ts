import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';

import { ApiService } from './core/api.service';
import { Health } from './core/models';

// App 外壳：顶部导航栏 + 内容区。
// 顶部显示当前研究的标的（从 /health 拿），下面是可切换的三个页面。
@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <header class="topbar">
      <div class="brand">
        📈 三毛量化投研看板
        <span class="asset" *ngIf="health">· {{ health.symbols.join(', ') }}</span>
      </div>
      <nav>
        <a routerLink="/signals" routerLinkActive="active">📌 今日信号</a>
        <a routerLink="/performance" routerLinkActive="active">💰 回测绩效</a>
        <a routerLink="/factors" routerLinkActive="active">🧩 因子库</a>
        <a routerLink="/factor-health" routerLinkActive="active">🩺 因子体检</a>
        <a routerLink="/regime" routerLinkActive="active">🌦️ 市场状态</a>
      </nav>
      <div class="status" [class.ok]="health" [class.down]="!health">
        {{ health ? '后端已连接' : '后端未连接' }}
      </div>
    </header>
    <main><router-outlet></router-outlet></main>
  `,
  styles: [`
    :host { display:block; font-family: -apple-system, "Segoe UI", "PingFang SC", sans-serif; color:#1f2937; }
    .topbar { display:flex; align-items:center; gap:24px; padding:12px 24px;
              background:#0f172a; color:#e2e8f0; }
    .brand { font-size:16px; font-weight:600; }
    .brand .asset { color:#7dd3fc; font-weight:400; font-size:14px; }
    nav { display:flex; gap:6px; }
    nav a { color:#cbd5e1; text-decoration:none; padding:6px 14px; border-radius:6px; font-size:14px; }
    nav a:hover { background:#1e293b; }
    nav a.active { background:#2563eb; color:#fff; }
    .status { margin-left:auto; font-size:12px; padding:4px 10px; border-radius:10px; }
    .status.ok { background:#052e16; color:#4ade80; }
    .status.down { background:#450a0a; color:#f87171; }
    main { padding: 20px 24px; max-width: 1280px; margin: 0 auto; }
  `],
})
export class AppComponent implements OnInit {
  private api = inject(ApiService);
  health?: Health;

  ngOnInit(): void {
    this.api.health().subscribe({ next: (h) => (this.health = h), error: () => (this.health = undefined) });
  }
}
