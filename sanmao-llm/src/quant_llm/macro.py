from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pandas as pd
import requests


# macro.py —— 宏观因子（影响整个市场的大环境指标）。
#
# 为什么需要宏观因子：
#   量价因子（ret_5d/vol_20d...）只看股票自己；舆情因子只看这只股票的新闻。
#   但科技股（如 NVDA）的涨跌，很大程度受“大环境”影响：
#     - 利率上升 -> 高估值科技股承压
#     - VIX（恐慌指数）飙升 -> 市场避险，抛售股票
#     - 美元走强 -> 影响资金流向
#   把这些大环境指标做成因子喂给模型，能补上量价+舆情看不到的一面。
#
# 数据怎么来：
#   用 FRED（美国圣路易斯联储官方数据库）的公开 CSV 下载接口 fredgraph.csv，
#   不需要 API key，且国内服务器可直连（Yahoo 在国内连不上，FRED 可以）。
#   三个系列：VIXCLS（VIX 收盘）、DGS10（10年期美债收益率，单位 %）、
#   DTWEXBGS（贸易加权广义美元指数）。宏观因子只需要 close 一条线，FRED 正合适。
#   结果缓存到 data/<strategy>/raw/fred_macro.csv，重复运行不重复联网。


# FRED 系列 ID -> 面板里的短名。
FRED_SERIES = {
    "VIXCLS": "vix",       # CBOE 波动率指数（恐慌指数）收盘
    "DGS10": "ust10y",     # 10年期美债收益率（单位 %，如 4.72 表示 4.72%）
    "DTWEXBGS": "dxy",     # 贸易加权广义美元指数（2006=100，只用变化率）
}

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"

# FRED 前面的 CDN 对 User-Agent 敏感：curl 系 UA 秒回，浏览器/自定义 UA 会被拖到超时。
# 实测（阿里云深圳 -> fred.stlouisfed.org）：curl/8.x 稳定 200，其余 ReadTimeout。
FRED_HEADERS = {"User-Agent": "curl/8.5.0"}

# 最终进模型的宏观因子列。build_macro_features 会生成这些列。
MACRO_FEATURE_COLUMNS = [
    "vix_level",         # VIX 当前水平（越高=市场越恐慌）
    "vix_change_5d",     # VIX 5日变化（快速升高=风险事件）
    "ust10y_level",      # 10年美债收益率水平（%）
    "ust10y_change_5d",  # 10年美债5日变化（利率快速上行压制科技股）
    "dxy_change_5d",     # 美元指数5日变化率
]


def _parse_fred_csv(text: str, short_name: str) -> pd.Series:
    """把 fredgraph.csv 的返回解析成一条以 date 为索引的数值序列。

    FRED 的 CSV 长这样（缺失日用 "." 占位）：
        observation_date,VIXCLS
        2026-08-03,15.86
        2026-08-04,.
    """
    frame = pd.read_csv(io.StringIO(text))
    if frame.shape[1] < 2:
        raise ValueError(f"Unexpected FRED csv shape for {short_name}: {frame.columns.tolist()}")
    date_col, value_col = frame.columns[0], frame.columns[1]
    series = pd.Series(
        pd.to_numeric(frame[value_col], errors="coerce").values,
        index=pd.to_datetime(frame[date_col]),
        name=short_name,
    )
    return series.dropna()


def fetch_macro_panel(
    start_date: str,
    end_date: str,
    data_dir: str | Path,
    allow_synthetic_fallback: bool = True,
) -> pd.DataFrame:
    """拉取宏观指标面板，返回宽表：date + vix + ust10y + dxy。

    有缓存读缓存（raw/fred_macro.csv），没缓存就逐个系列请求 FRED。
    某个系列拉失败时跳过它，不让整条链路挂掉；全部失败返回空面板，
    下游 join 会把宏观因子填 0。

    allow_synthetic_fallback 参数保留是为了兼容旧调用方；宏观数据
    从不合成假数据（合成的宏观因子比没有更糟），该参数在这里不生效。
    """
    del allow_synthetic_fallback  # 宏观因子不做 synthetic 兜底
    raw_dir = Path(data_dir) / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    cache_path = raw_dir / "fred_macro.csv"

    if cache_path.exists():
        panel = pd.read_csv(cache_path, parse_dates=["date"])
    else:
        series_list: list[pd.Series] = []
        for series_id, short in FRED_SERIES.items():
            try:
                resp = requests.get(
                    FRED_CSV_URL,
                    params={"id": series_id, "cosd": start_date, "coed": end_date},
                    headers=FRED_HEADERS,
                    timeout=30,
                )
                resp.raise_for_status()
                series_list.append(_parse_fred_csv(resp.text, short))
            except Exception:
                # 单个宏观指标拉不到就跳过，保证主链路能继续。
                continue

        if not series_list:
            # 全部失败：返回只有 date 列的空面板，下游 join 会把宏观因子填 0。
            return pd.DataFrame(columns=["date", *FRED_SERIES.values()])

        panel = pd.concat(series_list, axis=1).sort_index()
        # 三个系列的公布日历不完全一致（假期/数据源空洞），按日 forward-fill 对齐口径。
        panel = panel.ffill()
        # reset_index 出来的日期列名跟随原索引名（如 observation_date），统一改成 date。
        panel = panel.reset_index()
        panel = panel.rename(columns={panel.columns[0]: "date"})
        panel["date"] = pd.to_datetime(panel["date"]).dt.tz_localize(None).dt.normalize()
        panel.to_csv(cache_path, index=False)

    mask = (panel["date"] >= pd.Timestamp(start_date)) & (panel["date"] <= pd.Timestamp(end_date))
    return panel.loc[mask].reset_index(drop=True)


def build_macro_features(panel: pd.DataFrame) -> pd.DataFrame:
    """把宏观面板（水平值）转成宏观因子（水平 + 变化）。

    输出一张 date 索引的表，列是 MACRO_FEATURE_COLUMNS。
    """
    if panel.empty:
        return pd.DataFrame(columns=["date", *MACRO_FEATURE_COLUMNS])

    frame = panel.sort_values("date").copy()

    # 有哪个指标就算哪个，缺的列后面 join 时统一填 0。
    if "vix" in frame:
        frame["vix_level"] = frame["vix"]
        frame["vix_change_5d"] = frame["vix"].diff(5)
    if "ust10y" in frame:
        frame["ust10y_level"] = frame["ust10y"]
        frame["ust10y_change_5d"] = frame["ust10y"].diff(5)
    if "dxy" in frame:
        # 美元指数只用变化率（水平值量纲和别的差太多，用百分比变化更稳）。
        frame["dxy_change_5d"] = frame["dxy"].pct_change(5)

    present = [c for c in MACRO_FEATURE_COLUMNS if c in frame.columns]
    out = frame[["date", *present]].replace([np.inf, -np.inf], np.nan)
    return out.reset_index(drop=True)


def join_macro_features(price_features: pd.DataFrame, macro_features: pd.DataFrame) -> pd.DataFrame:
    """把宏观因子拼到价格特征上。

    和文本特征不同：宏观是“整个市场共享”的，不分股票，所以只按 date merge。
    how="left" 保留所有价格行；某天没有宏观数据就填 0（表示“无额外宏观信息”）。
    """
    merged = price_features.merge(macro_features, on="date", how="left")
    for column in MACRO_FEATURE_COLUMNS:
        if column not in merged.columns:
            merged[column] = 0.0
        # 强制数值化：宏观全拉失败时 merge 进来的是 object 空列，
        # 不转 float 会让 XGBoost 直接报 dtype 错误。
        merged[column] = pd.to_numeric(merged[column], errors="coerce").fillna(0.0)
    return merged
