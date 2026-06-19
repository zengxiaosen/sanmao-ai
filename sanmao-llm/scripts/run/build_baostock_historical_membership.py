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


def _load_trade_dates(start_date: str, end_date: str) -> pd.DataFrame:
    import baostock as bs

    rs = bs.query_trade_dates(start_date=start_date, end_date=end_date)
    frame = _query_rows(rs)
    if frame.empty:
        raise ValueError(f"No trade dates returned for {start_date} to {end_date}")
    frame = frame[frame["is_trading_day"] == "1"].copy()
    frame["calendar_date"] = pd.to_datetime(frame["calendar_date"])
    return frame


def _load_members_for_date(trade_date: str, universe: str) -> pd.DataFrame:
    import baostock as bs

    if universe == "hs300":
        rs = bs.query_hs300_stocks(trade_date)
    elif universe == "zz500":
        rs = bs.query_zz500_stocks(trade_date)
    elif universe == "sz50":
        rs = bs.query_sz50_stocks(trade_date)
    else:
        raise ValueError(f"Unsupported universe: {universe}")

    frame = _query_rows(rs)
    if frame.empty:
        return pd.DataFrame(columns=["date", "symbol"])
    frame["date"] = pd.to_datetime(frame["updateDate"])
    frame["symbol"] = frame["code"].map(baostock_code_to_symbol)
    return frame[["date", "symbol"]]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe", choices=["hs300", "zz500", "sz50"], required=True)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    import baostock as bs

    login = bs.login()
    if getattr(login, "error_code", "0") != "0":
        raise RuntimeError(f"BaoStock login failed: {getattr(login, 'error_msg', '')}")

    try:
        trade_dates = _load_trade_dates(args.start_date, args.end_date)
        frames: list[pd.DataFrame] = []
        for trade_date in trade_dates["calendar_date"].dt.strftime("%Y-%m-%d"):
            members = _load_members_for_date(trade_date, args.universe)
            if not members.empty:
                frames.append(members)
    finally:
        bs.logout()

    if not frames:
        raise ValueError(f"No membership rows built for universe={args.universe}")

    membership = pd.concat(frames, ignore_index=True).drop_duplicates().sort_values(["date", "symbol"]).reset_index(drop=True)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    membership.to_csv(output_path, index=False)
    print(f"saved {len(membership)} rows to {output_path} for universe={args.universe}")
    print(membership.head(10).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
