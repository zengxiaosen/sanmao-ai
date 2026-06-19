from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import os
from pathlib import Path


@dataclass(frozen=True)
class QmtConfig:
    """QMT / miniQMT 连接配置。

    QMT 通常不是互联网 REST API。
    它一般依赖：
      1. 本机安装并登录 QMT/miniQMT 客户端。
      2. Python 环境能 import xtquant。
      3. 有券商开通的模拟盘或实盘权限。

    当前适配器只做环境检测，不执行下单。
    """

    account_id: str
    account_type: str = "STOCK"
    client_path: str = ""
    session_id: int = 1001
    trading_mode: str = "paper"

    @classmethod
    def from_env(cls) -> "QmtConfig":
        return cls(
            account_id=os.environ.get("QMT_ACCOUNT_ID", ""),
            account_type=os.environ.get("QMT_ACCOUNT_TYPE", "STOCK"),
            client_path=os.environ.get("QMT_CLIENT_PATH", ""),
            session_id=int(os.environ.get("QMT_SESSION_ID", "1001")),
            trading_mode=os.environ.get("QMT_TRADING_MODE", "paper"),
        )


def check_qmt_environment(config: QmtConfig | None = None) -> dict:
    """检查当前机器是否具备连接 QMT 的基础条件。

    这个函数不会连接账户，也不会下单。
    只检查：
      1. xtquant 是否可 import。
      2. QMT_ACCOUNT_ID 是否配置。
      3. QMT_CLIENT_PATH 如果配置了，路径是否存在。
      4. trading_mode 是否仍处于 paper/simulation。
    """
    config = config or QmtConfig.from_env()
    xtquant_available = importlib.util.find_spec("xtquant") is not None
    client_path_exists = bool(config.client_path) and Path(config.client_path).exists()
    checks = {
        "xtquant_available": xtquant_available,
        "account_id_configured": bool(config.account_id),
        "client_path": config.client_path,
        "client_path_exists": client_path_exists,
        "session_id": config.session_id,
        "account_type": config.account_type,
        "trading_mode": config.trading_mode,
    }
    checks["ready_for_qmt_connection"] = (
        checks["xtquant_available"]
        and checks["account_id_configured"]
        and (not config.client_path or checks["client_path_exists"])
        and config.trading_mode in {"paper", "simulation", "sim"}
    )
    return checks


class QmtTradingClient:
    """QMT 交易适配器占位实现。

    这里先把接口边界定义出来：
      get_account
      get_positions
      submit_order

    等你拿到国金/银河/国信的 QMT 模拟盘和 xtquant 示例后，
    再在这些方法里填真实实现。
    """

    def __init__(self, config: QmtConfig | None = None) -> None:
        self.config = config or QmtConfig.from_env()
        self.environment = check_qmt_environment(self.config)
        if self.config.trading_mode not in {"paper", "simulation", "sim"}:
            raise ValueError("QMT live trading is disabled. Use paper/simulation first.")

    def assert_ready(self) -> None:
        """确认环境检测通过，否则拒绝继续调用 QMT 方法。"""
        if not self.environment["ready_for_qmt_connection"]:
            raise RuntimeError(f"QMT environment is not ready: {self.environment}")

    def get_account(self) -> dict:
        """预留：查询 QMT 账户资金。"""
        self.assert_ready()
        raise NotImplementedError("QMT get_account is pending xtquant integration and broker simulation confirmation.")

    def get_positions(self) -> list[dict]:
        """预留：查询 QMT 当前持仓。"""
        self.assert_ready()
        raise NotImplementedError("QMT get_positions is pending xtquant integration and broker simulation confirmation.")

    def submit_order(self, symbol: str, side: str, qty: int, price: float | None = None) -> dict:
        """预留：提交 QMT 模拟盘订单。

        注意：
          A 股数量必须先经过 market_rules 按 100 股一手取整。
        """
        self.assert_ready()
        raise NotImplementedError("QMT submit_order is pending xtquant integration and paper trading confirmation.")
