from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import os
import socket


@dataclass(frozen=True)
class FutuConfig:
    """富途牛牛 / Moomoo OpenD 连接配置。

    富途 OpenAPI 不是纯 REST。
    它需要一个 OpenD 网关：

      Python SDK -> OpenD host:port -> 富途服务器

    当前配置只用于检测 OpenD 是否可连接，不 unlock trade，不下单。
    """

    host: str = "127.0.0.1"
    port: int = 11111
    trading_mode: str = "paper"
    market: str = "HK"

    @classmethod
    def from_env(cls) -> "FutuConfig":
        return cls(
            host=os.environ.get("FUTU_OPEND_HOST", "127.0.0.1"),
            port=int(os.environ.get("FUTU_OPEND_PORT", "11111")),
            trading_mode=os.environ.get("FUTU_TRADING_MODE", "paper"),
            market=os.environ.get("FUTU_MARKET", "HK"),
        )


def check_futu_opend_environment(config: FutuConfig | None = None, timeout_seconds: float = 2.0) -> dict:
    """检查富途 OpenD 基础环境。

    这个函数不会 unlock trade，不会查真实资产，不会下单。
    只检查：
      1. futu Python SDK 是否安装。
      2. OpenD host:port 是否能 TCP 连通。
      3. trading_mode 是否仍是 paper/simulation。
    """
    config = config or FutuConfig.from_env()
    futu_sdk_available = importlib.util.find_spec("futu") is not None

    tcp_connected = False
    tcp_error = ""
    try:
        with socket.create_connection((config.host, config.port), timeout=timeout_seconds):
            tcp_connected = True
    except OSError as exc:
        tcp_error = str(exc)

    checks = {
        "futu_sdk_available": futu_sdk_available,
        "opend_host": config.host,
        "opend_port": config.port,
        "opend_tcp_connected": tcp_connected,
        "opend_tcp_error": tcp_error,
        "trading_mode": config.trading_mode,
        "market": config.market,
    }
    checks["ready_for_futu_connection"] = (
        futu_sdk_available and tcp_connected and config.trading_mode in {"paper", "simulation", "sim"}
    )
    return checks


class FutuTradingClient:
    """富途 OpenAPI 适配器占位实现。

    当前只做环境检测。
    等你开户并启动 OpenD 后，再接入：
      get_account
      get_positions
      submit_order
      broker reconciliation
    """

    def __init__(self, config: FutuConfig | None = None) -> None:
        self.config = config or FutuConfig.from_env()
        self.environment = check_futu_opend_environment(self.config)
        if self.config.trading_mode not in {"paper", "simulation", "sim"}:
            raise ValueError("Futu live trading is disabled. Use paper/simulation first.")

    def assert_ready(self) -> None:
        """确认 OpenD 和 SDK 检测通过，否则拒绝继续调用。"""
        if not self.environment["ready_for_futu_connection"]:
            raise RuntimeError(f"Futu OpenD environment is not ready: {self.environment}")

    def get_account(self) -> dict:
        """预留：查询富途模拟账户。"""
        self.assert_ready()
        raise NotImplementedError("Futu get_account is pending OpenD paper trading integration.")

    def get_positions(self) -> list[dict]:
        """预留：查询富途模拟持仓。"""
        self.assert_ready()
        raise NotImplementedError("Futu get_positions is pending OpenD paper trading integration.")

    def submit_order(self, symbol: str, side: str, qty: int, price: float | None = None) -> dict:
        """预留：提交富途模拟盘订单。

        注意：
          港股 lot size 后续要按具体股票处理，不能简单套用美股小数股逻辑。
        """
        self.assert_ready()
        raise NotImplementedError("Futu submit_order is pending OpenD paper trading integration.")
