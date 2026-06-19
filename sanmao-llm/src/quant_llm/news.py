from __future__ import annotations

import os
from pathlib import Path
import time

import pandas as pd
import requests


SEC_USER_AGENT = os.environ.get("SEC_USER_AGENT", "sanmao-quant-llm research contact@example.com")


def _sec_headers() -> dict[str, str]:
    return {"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate", "Host": "data.sec.gov"}


def load_sec_company_tickers() -> dict[str, str]:
    response = requests.get(
        "https://www.sec.gov/files/company_tickers.json",
        headers={"User-Agent": SEC_USER_AGENT},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    mapping: dict[str, str] = {}
    for item in payload.values():
        ticker = str(item["ticker"]).upper()
        mapping[ticker] = str(item["cik_str"]).zfill(10)
    return mapping


def fetch_sec_filings(
    symbols: list[str],
    start_date: str,
    end_date: str,
    forms: list[str] | None = None,
    limit_per_symbol: int = 50,
) -> pd.DataFrame:
    forms = forms or ["8-K", "10-Q", "10-K"]
    ticker_to_cik = load_sec_company_tickers()
    rows: list[dict] = []
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)

    for symbol in symbols:
        ticker = symbol.removesuffix(".US").upper()
        cik = ticker_to_cik.get(ticker)
        if not cik:
            raise ValueError(f"No SEC CIK found for {symbol}")

        response = requests.get(f"https://data.sec.gov/submissions/CIK{cik}.json", headers=_sec_headers(), timeout=30)
        response.raise_for_status()
        recent = response.json().get("filings", {}).get("recent", {})
        accession_numbers = recent.get("accessionNumber", [])
        form_list = recent.get("form", [])
        filing_dates = recent.get("filingDate", [])
        report_dates = recent.get("reportDate", [])
        primary_docs = recent.get("primaryDocument", [])

        count = 0
        for accession, form, filing_date, report_date, primary_doc in zip(
            accession_numbers, form_list, filing_dates, report_dates, primary_docs, strict=False
        ):
            if form not in forms:
                continue
            date = pd.Timestamp(filing_date)
            if date < start or date > end:
                continue
            accession_nodash = accession.replace("-", "")
            url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_nodash}/{primary_doc}"
            rows.append(
                {
                    "date": date,
                    "symbol": symbol,
                    "title": f"SEC filing {form} for {ticker}",
                    "body": f"{ticker} filed {form}. Filing date: {filing_date}. Report date: {report_date}.",
                    "source": "sec.gov",
                    "url": url,
                    "tags": form,
                    "cik": cik,
                    "form": form,
                    "accession_number": accession,
                }
            )
            count += 1
            if count >= limit_per_symbol:
                break

    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(
            columns=["date", "symbol", "title", "body", "source", "url", "tags", "cik", "form", "accession_number"]
        )
    return frame.sort_values(["symbol", "date"]).reset_index(drop=True)


def fetch_tiingo_news(
    symbols: list[str],
    start_date: str,
    end_date: str,
    limit: int = 100,
) -> pd.DataFrame:
    api_key = os.environ.get("TIINGO_API_KEY")
    if not api_key:
        raise ValueError("TIINGO_API_KEY is required to fetch Tiingo News")

    tickers = ",".join(symbol.removesuffix(".US") for symbol in symbols)
    response = requests.get(
        "https://api.tiingo.com/tiingo/news",
        params={
            "tickers": tickers,
            "startDate": start_date,
            "endDate": end_date,
            "limit": limit,
            "token": api_key,
        },
        timeout=30,
    )
    if response.status_code == 403:
        raise PermissionError(f"Tiingo News permission denied: {response.text}")
    response.raise_for_status()

    payload = response.json()
    if not isinstance(payload, list):
        raise ValueError(f"Unexpected Tiingo News response: {payload}")

    rows: list[dict] = []
    for item in payload:
        title = item.get("title") or ""
        description = item.get("description") or ""
        article = item.get("article") or ""
        published = item.get("publishedDate") or item.get("published_date")
        tags = item.get("tags") or []
        tickers_item = item.get("tickers") or []
        if not tickers_item:
            tickers_item = [symbol.removesuffix(".US") for symbol in symbols]
        for ticker in tickers_item:
            rows.append(
                {
                    "date": pd.Timestamp(published).normalize() if published else pd.NaT,
                    "symbol": f"{ticker}.US" if "." not in ticker else ticker,
                    "title": title,
                    "body": " ".join(part for part in [description, article] if part),
                    "source": item.get("source") or "",
                    "url": item.get("url") or "",
                    "tags": ",".join(str(tag) for tag in tags),
                }
            )

    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(columns=["date", "symbol", "title", "body", "source", "url", "tags"])
    frame = frame.dropna(subset=["date", "symbol"]).sort_values(["symbol", "date"]).reset_index(drop=True)
    return frame


def save_news_csv(news: pd.DataFrame, output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    news.to_csv(path, index=False)


DEFAULT_SYMBOL_QUERIES = {
    "AAPL.US": "Apple",
    "MSFT.US": "Microsoft",
    "NVDA.US": "Nvidia",
    "SPY.US": "Federal Reserve",
}


def fetch_gdelt_news(
    symbols: list[str],
    start_date: str,
    end_date: str,
    maxrecords_per_symbol: int = 50,
    symbol_queries: dict[str, str] | None = None,
) -> pd.DataFrame:
    symbol_queries = symbol_queries or DEFAULT_SYMBOL_QUERIES
    rows: list[dict] = []
    start_dt = pd.Timestamp(start_date).strftime("%Y%m%d000000")
    end_dt = pd.Timestamp(end_date).strftime("%Y%m%d235959")

    for symbol in symbols:
        query = symbol_queries.get(symbol, symbol.removesuffix(".US"))
        params = {
            "query": query,
            "mode": "ArtList",
            "format": "json",
            "maxrecords": maxrecords_per_symbol,
            "startdatetime": start_dt,
            "enddatetime": end_dt,
            "sort": "hybridrel",
        }
        response = _gdelt_get_with_retry(params)
        try:
            payload = response.json()
        except ValueError as exc:
            raise ValueError(f"GDELT returned non-JSON response for {symbol}: {response.text[:300]}") from exc
        for article in payload.get("articles", []):
            seen_date = article.get("seendate")
            rows.append(
                {
                    "date": pd.Timestamp(seen_date).normalize() if seen_date else pd.NaT,
                    "symbol": symbol,
                    "title": article.get("title") or "",
                    # GDELT ArtList does not include full body. Use title/source metadata for first-pass features.
                    "body": f"Source domain: {article.get('domain') or ''}. Language: {article.get('language') or ''}.",
                    "source": article.get("domain") or "gdelt",
                    "url": article.get("url") or "",
                    "tags": "gdelt",
                }
            )

    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(columns=["date", "symbol", "title", "body", "source", "url", "tags"])
    frame = frame.dropna(subset=["date", "symbol"]).drop_duplicates(subset=["symbol", "url"]).reset_index(drop=True)
    return frame.sort_values(["symbol", "date"]).reset_index(drop=True)


def _gdelt_get_with_retry(params: dict, attempts: int = 4) -> requests.Response:
    last_response: requests.Response | None = None
    for attempt in range(attempts):
        response = requests.get("https://api.gdeltproject.org/api/v2/doc/doc", params=params, timeout=45)
        if response.status_code != 429:
            response.raise_for_status()
            return response
        last_response = response
        time.sleep(2.0 * (attempt + 1))
    assert last_response is not None
    last_response.raise_for_status()
    return last_response
