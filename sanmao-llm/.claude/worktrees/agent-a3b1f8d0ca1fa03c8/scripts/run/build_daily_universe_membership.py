from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols-file", required=True, help="One symbol per line")
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--output", required=True, help="CSV with date,symbol")
    args = parser.parse_args()

    symbols = []
    for raw_line in Path(args.symbols_file).read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if line:
            symbols.append(line)
    if not symbols:
        raise ValueError(f"No symbols found in {args.symbols_file}")

    dates = pd.bdate_range(args.start_date, args.end_date)
    membership = pd.MultiIndex.from_product([dates, symbols], names=["date", "symbol"]).to_frame(index=False)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    membership.to_csv(output_path, index=False)
    print(f"saved {len(membership)} rows to {output_path} for {len(symbols)} symbols")
    print(membership.head(10).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
