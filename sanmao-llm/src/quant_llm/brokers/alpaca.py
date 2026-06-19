from __future__ import annotations

from dataclasses import dataclass
import os

import requests


@dataclass(frozen=True)
class AlpacaConfig:
    """Alpaca Paper Trading 连接配置。

    Alpaca 是当前美股模拟盘的 broker 样板：
      1. API 是 REST，部署简单。
      2. Paper endpoint 和 live endpoint 分离。
      3. 很适合验证“信号 -> 订单 -> 券商状态 -> 对账”这条工程链路。

    注意：
      默认只允许 paper endpoint。
      真实账户 live trading 必须经过单独安全审查后，才允许打开 allow_live_trading。
    """

    api_key_id: str
    api_secret_key: str
    base_url: str = "https://paper-api.alpaca.markets"
    allow_live_trading: bool = False

    @classmethod
    def from_env(cls, base_url: str | None = None, allow_live_trading: bool = False) -> "AlpacaConfig":
        api_key_id = os.environ.get("ALPACA_API_KEY_ID", "")
        api_secret_key = os.environ.get("ALPACA_API_SECRET_KEY", "")
        if not api_key_id or not api_secret_key:
            raise ValueError("ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY are required for Alpaca paper trading")

        return cls(
            api_key_id=api_key_id,
            api_secret_key=api_secret_key,
            base_url=base_url or os.environ.get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets"),
            allow_live_trading=allow_live_trading,
        )


class AlpacaTradingClient:
    """极简 Alpaca Trading API 客户端。

    这里没有引入额外 SDK，而是直接用 requests 调 REST API。
    这样做的原因：
      1. 依赖更少。
      2. 请求字段完全透明，便于你审计。
      3. 后续要替换成官方 SDK 时，只需要改这个文件。
    """

    def __init__(self, config: AlpacaConfig, session=None) -> None:
        # 安全边界：只要 base_url 不是 paper endpoint，就拒绝初始化。
        # 这样可以防止配置写错时误连真实账户。
        if "paper-api.alpaca.markets" not in config.base_url and not config.allow_live_trading:
            raise ValueError(
                "Refusing non-paper Alpaca base_url. Set allow_live_trading=True only after live-trading safety review."
            )
        self.config = config
        self.session = session or requests.Session()

    def _headers(self) -> dict[str, str]:
        return {
            "APCA-API-KEY-ID": self.config.api_key_id,
            "APCA-API-SECRET-KEY": self.config.api_secret_key,
            "accept": "application/json",
            "content-type": "application/json",
        }

    def get_account(self) -> dict:
        """读取 Alpaca paper account 的账户状态。"""
        response = self.session.get(f"{self.config.base_url}/v2/account", headers=self._headers(), timeout=30)
        response.raise_for_status()
        return response.json()

    def get_positions(self) -> list[dict]:
        """读取 Alpaca paper account 当前持仓。"""
        response = self.session.get(f"{self.config.base_url}/v2/positions", headers=self._headers(), timeout=30)
        response.raise_for_status()
        return response.json()

    def get_orders(self, status: str = "all", limit: int = 50) -> list[dict]:
        """读取 Alpaca paper account 订单。

        status:
          open：未完成订单。
          closed：已完成/取消订单。
          all：全部订单。排查 accepted 但未 filled 的订单时很有用。
        """
        response = self.session.get(
            f"{self.config.base_url}/v2/orders",
            headers=self._headers(),
            params={"status": status, "limit": limit, "direction": "desc"},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def submit_market_order(self, symbol: str, side: str, qty: float, time_in_force: str = "day") -> dict:
        """提交 Alpaca paper market order。

        参数说明：
          symbol:
            Alpaca 使用 `AAPL`，项目内部可能使用 `AAPL.US`。
            调用前要先用 alpaca_symbol(...) 做转换。

          side:
            buy 或 sell。

          qty:
            股数。Alpaca paper 对部分标的支持小数股。
        """
        payload = {
            "symbol": symbol,
            "qty": f"{qty:.6f}",
            "side": side,
            "type": "market",
            "time_in_force": time_in_force,
        }
        response = self.session.post(f"{self.config.base_url}/v2/orders", headers=self._headers(), json=payload, timeout=30)
        response.raise_for_status()
        return response.json()


def alpaca_symbol(project_symbol: str) -> str:
    """把项目内部 symbol 转成 Alpaca symbol。

    项目内部为了区分市场，常用 `AAPL.US`。
    Alpaca 下单接口只需要 `AAPL`。
    """
    return project_symbol.removesuffix(".US")
