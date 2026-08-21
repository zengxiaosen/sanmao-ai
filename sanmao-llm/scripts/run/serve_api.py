from __future__ import annotations

import os
import sys


# serve_api.py —— 启动看板后端（FastAPI + uvicorn）。
#
# 用法：
#   cd /root/sanmao-ai/sanmao-llm
#   SANMAO_CONFIG=config/nvda_single_asset.yaml .venv/bin/python scripts/run/serve_api.py
#
# 默认监听 0.0.0.0:8000。Angular 看板（:4200）会请求这个地址。
# SANMAO_CONFIG 指定服务哪个策略的结果（默认 config/nvda_single_asset.yaml）。


def main() -> int:
    import uvicorn

    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "8000"))
    os.environ.setdefault("SANMAO_CONFIG", "config/nvda_single_asset.yaml")

    print(f"Serving Sanmao Quant Dashboard API on http://{host}:{port}")
    print(f"Strategy config: {os.environ['SANMAO_CONFIG']}")
    uvicorn.run("quant_api.main:app", host=host, port=port, reload=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
