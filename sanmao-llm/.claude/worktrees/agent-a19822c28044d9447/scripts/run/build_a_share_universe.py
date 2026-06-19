from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from quant_llm.data import baostock_code_to_symbol


def _query_rows(result) -> pd.DataFrame:
    rows: list[list[str]] = []
    while result.next():
        rows.append(result.get_row_data())
    return pd.DataFrame(rows, columns=result.fields)


def _load_baostock_universe(trade_date: str, universe: str) -> pd.DataFrame:
    import baostock as bs

    login = bs.login()
    if getattr(login, "error_code", "0") != "0":
        raise RuntimeError(f"BaoStock login failed: {getattr(login, 'error_msg', '')}")

    try:
        if universe == "all":
            members = _query_rows(bs.query_all_stock(trade_date))
        elif universe == "hs300":
            members = _query_rows(bs.query_hs300_stocks(trade_date))
        elif universe == "zz500":
            members = _query_rows(bs.query_zz500_stocks(trade_date))
        elif universe == "sz50":
            members = _query_rows(bs.query_sz50_stocks(trade_date))
        else:
            raise ValueError(f"Unsupported universe: {universe}")

        if members.empty:
            raise ValueError(f"BaoStock returned no rows for universe={universe} trade_date={trade_date}")

        basics = []
        for code in members["code"].drop_duplicates():
            frame = _query_rows(bs.query_stock_basic(code=code))
            if not frame.empty:
                basics.append(frame)
        basic_frame = pd.concat(basics, ignore_index=True) if basics else pd.DataFrame()
    finally:
        bs.logout()

    if basic_frame.empty:
        raise ValueError("BaoStock stock_basic returned no rows")

    merged = members.merge(basic_frame, on="code", how="left", suffixes=("", "_basic"))
    merged["symbol"] = merged["code"].map(baostock_code_to_symbol)
    merged["ipoDate"] = pd.to_datetime(merged["ipoDate"], errors="coerce")
    merged["outDate"] = pd.to_datetime(merged["outDate"], errors="coerce")
    return merged


def _apply_filters(frame: pd.DataFrame, trade_date: str, min_listing_days: int) -> pd.DataFrame:
    as_of = pd.Timestamp(trade_date)
    filtered = frame.copy()
    filtered = filtered[filtered["type"] == "1"]
    filtered = filtered[filtered["status"] == "1"]
    filtered = filtered[filtered["ipoDate"].notna()]
    filtered = filtered[(as_of - filtered["ipoDate"]).dt.days >= min_listing_days]
    filtered = filtered[filtered["outDate"].isna() | (filtered["outDate"] > as_of)]
    filtered = filtered[~filtered["code_name"].fillna("").str.contains("ST", case=False, regex=False)]
    return filtered.sort_values("symbol").reset_index(drop=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trade-date", required=True, help="Universe snapshot date, e.g. 2026-05-29")
    parser.add_argument(
        "--universe",
        choices=["all", "hs300", "zz500", "sz50"],
        default="all",
        help="Which BaoStock universe to query",
    )
    parser.add_argument("--min-listing-days", type=int, default=120)
    parser.add_argument("--output", required=True, help="Output text file path, one symbol per line")
    args = parser.parse_args()

    universe = _load_baostock_universe(args.trade_date, args.universe)
    filtered = _apply_filters(universe, args.trade_date, args.min_listing_days)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(filtered["symbol"].tolist()) + "\n", encoding="utf-8")

    print(
        f"saved {len(filtered)} symbols to {output_path} "
        f"(raw={len(universe)}, universe={args.universe}, min_listing_days={args.min_listing_days})"
    )
    print(filtered[["symbol", "code_name", "ipoDate"]].head(20).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
