from __future__ import annotations

import argparse
from pathlib import Path

from quant_llm.data import load_price_panel
from quant_llm.config import load_config


def main() -> int:
    """拉取 BaoStock A 股日线数据并保存为 CSV。

    这个脚本只验证数据源，不训练模型、不下单。
    真正训练/回测可以直接运行：
      .venv/bin/python scripts/run/run_baseline.py --config config/a_share_baostock.yaml
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/a_share_baostock.yaml")
    args = parser.parse_args()

    config = load_config(args.config)
    data_dir = Path(config["data_dir"])
    data_dir.mkdir(parents=True, exist_ok=True)

    prices = load_price_panel(
        config["symbols"],
        config["start_date"],
        config["end_date"],
        data_dir,
        allow_synthetic_fallback=config.get("allow_synthetic_fallback", False),
        provider=config.get("market_data_provider", "baostock"),
    )
    output = data_dir / "features" / "a_share_prices.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    prices.to_csv(output, index=False)
    print(f"saved {len(prices)} A-share rows for {len(config['symbols'])} symbols to {output}")
    print(prices.tail(10).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
