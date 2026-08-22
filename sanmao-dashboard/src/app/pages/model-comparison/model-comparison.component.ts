import { Component, OnInit } from "@angular/core";
import { CommonModule } from "@angular/common";
import { HttpClient } from "@angular/common/http";
import { Chart, registerables } from "chart.js";

Chart.register(...registerables);

@Component({
  selector: "app-model-comparison",
  standalone: true,
  imports: [CommonModule],
  templateUrl: "./model-comparison.component.html",
  styleUrls: ["./model-comparison.component.scss"]
})
export class ModelComparisonComponent implements OnInit {
  data: any = null;
  loading = true;
  
  constructor(private http: HttpClient) {}
  
  ngOnInit() {
    this.loadData();
  }
  
  loadData() {
    this.http.get("/assets/backtest_comparison.json").subscribe({
      next: (data: any) => {
        this.data = data;
        this.loading = false;
        setTimeout(() => this.renderCharts(), 100);
      },
      error: (err) => {
        console.error("Failed to load comparison data:", err);
        this.loading = false;
      }
    });
  }
  
  renderCharts() {
    this.renderCumulativeChart();
    this.renderDrawdownChart();
    this.renderMetricsRadar();
  }
  
  renderCumulativeChart() {
    const canvas = document.getElementById("cumulativeChart") as HTMLCanvasElement;
    if (!canvas) return;
    
    const single = this.data.models.single.cumulative_curve;
    const ensemble = this.data.models.ensemble.cumulative_curve;
    
    new Chart(canvas, {
      type: "line",
      data: {
        labels: single.map((d: any) => d.date),
        datasets: [
          {
            label: "单模型",
            data: single.map((d: any) => (d.cumulative - 1) * 100),
            borderColor: "#3b82f6",
            backgroundColor: "rgba(59, 130, 246, 0.1)",
            borderWidth: 2,
            pointRadius: 0,
          },
          {
            label: "集成模型",
            data: ensemble.map((d: any) => (d.cumulative - 1) * 100),
            borderColor: "#10b981",
            backgroundColor: "rgba(16, 185, 129, 0.1)",
            borderWidth: 2,
            pointRadius: 0,
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          title: { display: true, text: "累计收益对比 (%)" },
          legend: { position: "top" }
        },
        scales: {
          y: { beginAtZero: true }
        }
      }
    });
  }
  
  renderDrawdownChart() {
    const canvas = document.getElementById("drawdownChart") as HTMLCanvasElement;
    if (!canvas) return;
    
    const single = this.data.models.single.drawdown_curve;
    const ensemble = this.data.models.ensemble.drawdown_curve;
    
    new Chart(canvas, {
      type: "line",
      data: {
        labels: single.map((d: any) => d.date),
        datasets: [
          {
            label: "单模型",
            data: single.map((d: any) => d.drawdown * 100),
            borderColor: "#ef4444",
            backgroundColor: "rgba(239, 68, 68, 0.1)",
            borderWidth: 2,
            pointRadius: 0,
            fill: true,
          },
          {
            label: "集成模型",
            data: ensemble.map((d: any) => d.drawdown * 100),
            borderColor: "#f59e0b",
            backgroundColor: "rgba(245, 158, 11, 0.1)",
            borderWidth: 2,
            pointRadius: 0,
            fill: true,
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          title: { display: true, text: "回撤对比 (%)" },
          legend: { position: "top" }
        },
        scales: {
          y: { 
            reverse: true,
            ticks: {
              callback: (value: any) => Math.abs(value as number).toFixed(1) + "%"
            }
          }
        }
      }
    });
  }
  
  renderMetricsRadar() {
    const canvas = document.getElementById("metricsRadar") as HTMLCanvasElement;
    if (!canvas) return;
    
    const single = this.data.models.single.metrics;
    const ensemble = this.data.models.ensemble.metrics;
    
    new Chart(canvas, {
      type: "radar",
      data: {
        labels: ["总收益", "年化收益", "夏普×20", "回撤（负）", "胜率"],
        datasets: [
          {
            label: "单模型",
            data: [
              single.total_return,
              single.annualized_return,
              single.sharpe_ratio * 20,
              -single.max_drawdown,
              single.win_rate
            ],
            borderColor: "#3b82f6",
            backgroundColor: "rgba(59, 130, 246, 0.2)",
            borderWidth: 2,
          },
          {
            label: "集成模型",
            data: [
              ensemble.total_return,
              ensemble.annualized_return,
              ensemble.sharpe_ratio * 20,
              -ensemble.max_drawdown,
              ensemble.win_rate
            ],
            borderColor: "#10b981",
            backgroundColor: "rgba(16, 185, 129, 0.2)",
            borderWidth: 2,
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          title: { display: true, text: "综合指标雷达图" }
        },
        scales: {
          r: {
            beginAtZero: true,
            max: 100
          }
        }
      }
    });
  }
}
