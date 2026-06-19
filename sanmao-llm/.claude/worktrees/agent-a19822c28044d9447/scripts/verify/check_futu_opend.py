from __future__ import annotations

import json

from quant_llm.broker import FutuConfig, check_futu_opend_environment
from quant_llm.config import load_project_env


def main() -> int:
    """检查富途牛牛 / Moomoo OpenD 是否可连接。

    这个脚本不会 unlock trade，不会查真实资产，不会下单。
    它只检查：
      - futu Python SDK 是否安装
      - FUTU_OPEND_HOST:FUTU_OPEND_PORT 是否能 TCP 连接
      - trading_mode 是否是 paper/simulation
    """
    load_project_env()
    result = check_futu_opend_environment(FutuConfig.from_env())
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if result["ready_for_futu_connection"]:
        print("Futu OpenD basic checks passed.")
    else:
        print("Futu OpenD is not ready yet. Install futu-api, start OpenD, and check FUTU_OPEND_HOST/PORT.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
