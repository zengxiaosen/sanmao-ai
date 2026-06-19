from __future__ import annotations

import json

from quant_llm.broker import QmtConfig, check_qmt_environment
from quant_llm.config import load_project_env


def main() -> int:
    """检查国金 QMT / miniQMT Python 环境是否准备好。

    这个脚本不会连接账户、不会下单，只做本机环境诊断。
    你安装国金 QMT 后，先运行它。
    """
    load_project_env()
    result = check_qmt_environment(QmtConfig.from_env())
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if result["ready_for_qmt_connection"]:
        print("QMT environment basic checks passed.")
    else:
        print("QMT environment is not ready yet. Check xtquant, QMT_ACCOUNT_ID, and QMT_CLIENT_PATH.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
