import { ApplicationConfig } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { provideEchartsCore } from 'ngx-echarts';

import { routes } from './app.routes';

// 这里给整个 App 开通两个全局能力：
//   provideHttpClient —— 允许向后端 FastAPI 发网络请求（取因子/信号/回测数据）。
//   provideEchartsCore —— 注册 echarts 图表库，按需加载（体积更小）。
export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(routes),
    provideHttpClient(),
    provideEchartsCore({ echarts: () => import('echarts') }),
  ],
};
