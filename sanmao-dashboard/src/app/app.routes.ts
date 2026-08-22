import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', redirectTo: 'signals', pathMatch: 'full' },
  {
    path: 'factors',
    loadComponent: () =>
      import('./pages/factor-library/factor-library.component').then((m) => m.FactorLibraryComponent),
  },
  {
    path: 'signals',
    loadComponent: () =>
      import('./pages/signals/signals.component').then((m) => m.SignalsComponent),
  },
  {
    path: 'performance',
    loadComponent: () =>
      import('./pages/performance/performance.component').then((m) => m.PerformanceComponent),
  },
  {
    path: 'factor-health',
    loadComponent: () =>
      import('./pages/factor-health/factor-health.component').then((m) => m.FactorHealthComponent),
  },
  {
    path: 'regime',
    loadComponent: () =>
      import('./pages/regime-review/regime-review.component').then((m) => m.RegimeReviewComponent),
  },
  {
    path: 'model-comparison',
    loadComponent: () =>
      import('./pages/model-comparison/model-comparison.component').then((m) => m.ModelComparisonComponent),
  },
];
