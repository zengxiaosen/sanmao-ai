import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import {
  Health, FactorsResponse, SignalsResponse, BacktestResponse,
  FactorAnalyticsResponse, RegimeResponse, ReviewResponse,
} from './models';

// ApiService —— 看板的「数据跑腿小哥」。
// 页面不直接发网络请求，而是调用这里的方法，逻辑集中、好维护。
@Injectable({ providedIn: 'root' })
export class ApiService {
  private http = inject(HttpClient);
  private base = environment.apiBaseUrl;

  health(): Observable<Health> {
    return this.http.get<Health>(`${this.base}/health`);
  }

  factors(limit = 60): Observable<FactorsResponse> {
    return this.http.get<FactorsResponse>(`${this.base}/factors`, { params: { limit } });
  }

  signals(limit = 250): Observable<SignalsResponse> {
    return this.http.get<SignalsResponse>(`${this.base}/signals`, { params: { limit } });
  }

  backtest(limit = 2000): Observable<BacktestResponse> {
    return this.http.get<BacktestResponse>(`${this.base}/backtest`, { params: { limit } });
  }

  factorAnalytics(): Observable<FactorAnalyticsResponse> {
    return this.http.get<FactorAnalyticsResponse>(`${this.base}/factor-analytics`);
  }

  regime(): Observable<RegimeResponse> {
    return this.http.get<RegimeResponse>(`${this.base}/regime`);
  }

  review(): Observable<ReviewResponse> {
    return this.http.get<ReviewResponse>(`${this.base}/review`);
  }
}
