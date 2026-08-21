from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone
import os
from pathlib import Path

import numpy as np
import pandas as pd
import requests


@dataclass(frozen=True)
class PriceSource:
    raw_dir: Path
    allow_synthetic_fallback: bool = False
    provider: str = "yfinance"

    def __post_init__(self) -> None:
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def load_symbol(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        cache_path = self.raw_dir / f"{self.provider}_{symbol.replace('.', '_')}.csv"
        if cache_path.exists():
            frame = pd.read_csv(cache_path, parse_dates=["date"])
            if "data_provider_used" not in frame.columns:
                frame["data_provider_used"] = "cached_unknown"
        else:
            provider_used = self.provider
            try:
                frame = self._load_uncached(symbol, start_date, end_date)
            except Exception:
                if not self.allow_synthetic_fallback:
                    raise
                frame = self._generate_synthetic(symbol, start_date, end_date)
                provider_used = "synthetic_fallback"
            frame["data_provider_used"] = provider_used
            frame.to_csv(cache_path, index=False)

        mask = (frame["date"] >= pd.Timestamp(start_date)) & (frame["date"] <= pd.Timestamp(end_date))
        frame = frame.loc[mask].copy()
        frame["symbol"] = symbol
        frame["data_provider_requested"] = self.provider
        return frame.sort_values(["symbol", "date"]).reset_index(drop=True)

    def _load_uncached(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        if self.provider == "synthetic":
            return self._generate_synthetic(symbol, start_date, end_date)
        if self.provider == "yfinance":
            return self._download_yfinance(symbol, start_date, end_date)
        if self.provider == "yahoo_chart":
            return self._download_yahoo_chart(symbol, start_date, end_date)
        if self.provider == "alpha_vantage":
            return self._download_alpha_vantage(symbol, start_date, end_date)
        if self.provider == "tiingo":
            return self._download_tiingo(symbol, start_date, end_date)
        if self.provider == "tencent":
            return self._download_tencent(symbol, start_date, end_date)
        if self.provider == "baostock":
            return self._download_baostock(symbol, start_date, end_date)
        raise ValueError(f"Unknown market data provider: {self.provider}")

    def _baostock_symbol(self, symbol: str) -> str:
        """把项目内部 A 股 symbol 转成 BaoStock symbol。

        项目内部统一用：
          600000.SH
          000001.SZ

        BaoStock 需要：
          sh.600000
          sz.000001

        这里只处理 A 股普通格式。后续如果接指数、基金、港股，需要单独扩展。
        """
        upper = symbol.upper()
        if upper.endswith(".SH"):
            return "sh." + upper.removesuffix(".SH")
        if upper.endswith(".SZ"):
            return "sz." + upper.removesuffix(".SZ")
        if upper.startswith("SH."):
            return "sh." + upper.removeprefix("SH.")
        if upper.startswith("SZ."):
            return "sz." + upper.removeprefix("SZ.")
        raise ValueError(f"BaoStock symbol must end with .SH or .SZ: {symbol}")

    def _download_baostock(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """用 BaoStock 下载 A 股日线 OHLCV。

        BaoStock 的定位：
          1. 免费 A 股历史数据源。
          2. 适合先做 A 股离线研究和回测。
          3. 不是券商交易接口，不能下单。

        复权说明：
          adjustflag=2 表示前复权。历史回测通常更适合用复权价，
          但真实交易/下单前还需要用未复权价格和实际成交规则重新核对。
        """
        import baostock as bs

        login = bs.login()
        if getattr(login, "error_code", "0") != "0":
            raise RuntimeError(f"BaoStock login failed: {getattr(login, 'error_msg', '')}")

        try:
            result = bs.query_history_k_data_plus(
                self._baostock_symbol(symbol),
                "date,open,high,low,close,volume",
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag="2",
            )
            if getattr(result, "error_code", "0") != "0":
                raise RuntimeError(f"BaoStock query failed for {symbol}: {getattr(result, 'error_msg', '')}")

            rows = []
            while result.next():
                rows.append(result.get_row_data())
            frame = pd.DataFrame(rows, columns=result.fields)
            if frame.empty:
                raise ValueError(f"No BaoStock daily data returned for {symbol}")
            return self._normalize_ohlcv(frame, symbol)
        finally:
            bs.logout()

    def _download_yfinance(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        import yfinance as yf

        yahoo_symbol = symbol.removesuffix(".US")
        # yfinance end is exclusive; add one day so config end_date is included.
        end_exclusive = (pd.Timestamp(end_date) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        raw = yf.download(
            yahoo_symbol,
            start=start_date,
            end=end_exclusive,
            auto_adjust=True,
            progress=False,
            threads=False,
        )
        if raw.empty:
            raise ValueError(f"No yfinance data returned for {symbol}")

        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        frame = raw.reset_index()
        frame.columns = [str(column).strip().lower().replace(" ", "_") for column in frame.columns]
        rename = {"date": "date", "open": "open", "high": "high", "low": "low", "close": "close", "volume": "volume"}
        frame = frame.rename(columns=rename)
        return self._normalize_ohlcv(frame, symbol)

    def _download_alpha_vantage(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        api_key = os.environ.get("ALPHA_VANTAGE_API_KEY")
        if not api_key:
            raise ValueError("ALPHA_VANTAGE_API_KEY is required for market_data_provider=alpha_vantage")

        response = requests.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "TIME_SERIES_DAILY_ADJUSTED",
                "symbol": symbol.removesuffix(".US"),
                "outputsize": "full",
                "apikey": api_key,
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if "Note" in payload or "Information" in payload:
            raise ValueError(f"Alpha Vantage limit/info response for {symbol}: {payload}")
        series = payload.get("Time Series (Daily)")
        if not series:
            raise ValueError(f"No Alpha Vantage daily adjusted data returned for {symbol}: {payload}")

        rows = []
        for date, values in series.items():
            rows.append(
                {
                    "date": date,
                    "open": values.get("1. open"),
                    "high": values.get("2. high"),
                    "low": values.get("3. low"),
                    # Use adjusted close to account for splits/dividends in long historical backtests.
                    "close": values.get("5. adjusted close") or values.get("4. close"),
                    "volume": values.get("6. volume"),
                }
            )
        frame = pd.DataFrame(rows)
        mask = (pd.to_datetime(frame["date"]) >= pd.Timestamp(start_date)) & (pd.to_datetime(frame["date"]) <= pd.Timestamp(end_date))
        return self._normalize_ohlcv(frame.loc[mask], symbol)

    def _download_tiingo(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        api_key = os.environ.get("TIINGO_API_KEY")
        if not api_key:
            raise ValueError("TIINGO_API_KEY is required for market_data_provider=tiingo")

        ticker = symbol.removesuffix(".US")
        response = requests.get(
            f"https://api.tiingo.com/tiingo/daily/{ticker}/prices",
            params={
                "startDate": start_date,
                "endDate": end_date,
                "format": "json",
                "token": api_key,
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list) or not payload:
            raise ValueError(f"No Tiingo daily data returned for {symbol}: {payload}")

        raw = pd.DataFrame(payload)
        frame = pd.DataFrame(
            {
                "date": raw["date"],
                # Adjusted prices are preferred for historical backtests because they account for splits/dividends.
                "open": raw.get("adjOpen", raw["open"]),
                "high": raw.get("adjHigh", raw["high"]),
                "low": raw.get("adjLow", raw["low"]),
                "close": raw.get("adjClose", raw["close"]),
                "volume": raw.get("adjVolume", raw["volume"]),
            }
        )
        return self._normalize_ohlcv(frame, symbol)

    def _tencent_symbol(self, symbol: str) -> str:
        """把项目内部美股 symbol 转成腾讯行情接口的 symbol。

        腾讯接口格式：us + 代码 + 交易所后缀（.OQ=纳斯达克，.N=纽交所）。
        例如 NVDA.US -> usNVDA.OQ。这里默认试 .OQ，拉不到再由调用方试 .N。
        """
        return "us" + symbol.removesuffix(".US").upper()

    @staticmethod
    def _parse_tencent_payload(payload: dict, tencent_symbol: str) -> list[list]:
        """从腾讯 K 线接口的 JSON 里取出日线行。

        返回行格式（腾讯约定）：[date, open, close, high, low, volume, ...]。
        没有数据时返回空列表。
        """
        data = payload.get("data")
        if not isinstance(data, dict):
            return []
        entry = data.get(tencent_symbol)
        if not isinstance(entry, dict):
            return []
        # 前复权键叫 qfqday，不复权叫 day；哪个有用哪个。
        for key in ("qfqday", "day"):
            rows = entry.get(key)
            if isinstance(rows, list) and rows:
                return rows
        return []

    def _download_tencent(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """用腾讯行情接口下载美股日线（前复权）。

        选它的原因：免费、无需 API key，而且国内服务器可以直连
        （Yahoo/stooq 在国内连不上，Tiingo/AlphaVantage 要注册 key）。

        接口单次最多返回约 320~800 行，且按 end_date 往前数，
        所以这里按自然年分页请求再拼起来。
        """
        start = pd.Timestamp(start_date)
        end = pd.Timestamp(end_date)
        frames: list[pd.DataFrame] = []

        for exchange_suffix in (".OQ", ".N"):
            tencent_symbol = self._tencent_symbol(symbol) + exchange_suffix
            frames = []
            for year in range(start.year, end.year + 1):
                seg_start = max(start, pd.Timestamp(f"{year}-01-01")).strftime("%Y-%m-%d")
                seg_end = min(end, pd.Timestamp(f"{year}-12-31")).strftime("%Y-%m-%d")
                response = requests.get(
                    "https://web.ifzq.gtimg.cn/appstock/app/usfqkline/get",
                    params={"param": f"{tencent_symbol},day,{seg_start},{seg_end},320,qfq"},
                    headers={"User-Agent": "sanmao-quant-llm/0.1"},
                    timeout=30,
                )
                response.raise_for_status()
                rows = self._parse_tencent_payload(response.json(), tencent_symbol)
                if not rows:
                    continue
                frames.append(
                    pd.DataFrame(
                        {
                            "date": [r[0] for r in rows],
                            "open": [r[1] for r in rows],
                            "close": [r[2] for r in rows],
                            "high": [r[3] for r in rows],
                            "low": [r[4] for r in rows],
                            "volume": [r[5] for r in rows],
                        }
                    )
                )
            if frames:
                break  # .OQ 拉到了就不用再试 .N

        if not frames:
            raise ValueError(f"No Tencent daily data returned for {symbol}")

        frame = pd.concat(frames, ignore_index=True)
        # 接口按 end_date 往前数 320 行，可能带出上一年的尾巴，去重并裁剪到请求区间。
        frame = frame.drop_duplicates(subset=["date"], keep="last")
        frame["date"] = pd.to_datetime(frame["date"])
        mask = (frame["date"] >= start) & (frame["date"] <= end)
        return self._normalize_ohlcv(frame.loc[mask].sort_values("date"), symbol)

    def _download_yahoo_chart(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        yahoo_symbol = symbol.removesuffix(".US")
        period1 = int(pd.Timestamp(start_date, tz=timezone.utc).timestamp())
        period2 = int((pd.Timestamp(end_date, tz=timezone.utc) + pd.Timedelta(days=1)).timestamp())
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
        response = requests.get(
            url,
            params={
                "period1": period1,
                "period2": period2,
                "interval": "1d",
                "events": "history",
                "includeAdjustedClose": "true",
            },
            headers={"User-Agent": "sanmao-quant-llm/0.1"},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        result = payload.get("chart", {}).get("result")
        if not result:
            raise ValueError(f"No Yahoo chart data returned for {symbol}: {payload.get('chart', {}).get('error')}")

        item = result[0]
        timestamps = item.get("timestamp") or []
        quote = (item.get("indicators", {}).get("quote") or [{}])[0]
        adjusted = (item.get("indicators", {}).get("adjclose") or [{}])[0].get("adjclose")
        frame = pd.DataFrame(
            {
                "date": pd.to_datetime(timestamps, unit="s", utc=True).tz_convert(None).normalize(),
                "open": quote.get("open"),
                "high": quote.get("high"),
                "low": quote.get("low"),
                "close": adjusted or quote.get("close"),
                "volume": quote.get("volume"),
            }
        )
        return self._normalize_ohlcv(frame, symbol)

    def _normalize_ohlcv(self, frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
        required = ["date", "open", "high", "low", "close", "volume"]
        missing = [column for column in required if column not in frame.columns]
        if missing:
            raise ValueError(f"Missing OHLCV columns for {symbol}: {missing}")

        normalized = frame[required].copy()
        normalized["date"] = pd.to_datetime(normalized["date"], utc=False).dt.tz_localize(None).dt.normalize()
        for column in ["open", "high", "low", "close", "volume"]:
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
        normalized = normalized.dropna(subset=required)
        if normalized.empty:
            raise ValueError(f"Market data was empty after cleaning for {symbol}")
        return normalized

    def _generate_synthetic(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        dates = pd.bdate_range(start_date, end_date)
        seed = sum(ord(char) for char in symbol)
        rng = np.random.default_rng(seed)
        market = rng.normal(0.00025, 0.012, size=len(dates))
        trend = np.sin(np.linspace(0, 18, len(dates))) * 0.0015
        returns = market + trend + rng.normal(0, 0.006, size=len(dates))
        close = 100.0 * np.cumprod(1.0 + returns)
        open_ = close * (1.0 + rng.normal(0, 0.002, size=len(dates)))
        high = np.maximum(open_, close) * (1.0 + rng.uniform(0.001, 0.015, size=len(dates)))
        low = np.minimum(open_, close) * (1.0 - rng.uniform(0.001, 0.015, size=len(dates)))
        volume = rng.integers(1_000_000, 12_000_000, size=len(dates))
        return pd.DataFrame(
            {
                "date": dates,
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            }
        )


def load_price_panel(
    symbols: list[str],
    start_date: str,
    end_date: str,
    data_dir: str | Path,
    allow_synthetic_fallback: bool = False,
    provider: str = "yfinance",
) -> pd.DataFrame:
    source = PriceSource(Path(data_dir) / "raw", allow_synthetic_fallback=allow_synthetic_fallback, provider=provider)
    frames = [source.load_symbol(symbol, start_date, end_date) for symbol in symbols]
    return pd.concat(frames, ignore_index=True).sort_values(["symbol", "date"]).reset_index(drop=True)


def baostock_code_to_symbol(code: str) -> str:
    upper = code.upper()
    if upper.startswith("SH."):
        return upper.removeprefix("SH.") + ".SH"
    if upper.startswith("SZ."):
        return upper.removeprefix("SZ.") + ".SZ"
    raise ValueError(f"BaoStock code must start with sh. or sz.: {code}")


def load_universe_membership(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path, parse_dates=["date"])
    required = {"date", "symbol"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Universe membership file missing columns {sorted(missing)}: {path}")
    frame["date"] = pd.to_datetime(frame["date"]).dt.tz_localize(None).dt.normalize()
    frame["symbol"] = frame["symbol"].astype(str)
    return frame[["date", "symbol"]].drop_duplicates().sort_values(["date", "symbol"]).reset_index(drop=True)


def apply_universe_membership(prices: pd.DataFrame, membership: pd.DataFrame) -> pd.DataFrame:
    filtered = prices.merge(membership.assign(in_universe=1), on=["date", "symbol"], how="inner")
    if filtered.empty:
        raise ValueError("No price rows left after applying universe membership")
    return filtered.drop(columns=["in_universe"]).reset_index(drop=True)
