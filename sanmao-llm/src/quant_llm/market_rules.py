from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class MarketRules:
    """市场规则层。

    策略模型只负责输出“想要多少目标仓位”，但不同市场的交易规则不同：
      - 美股 Alpaca paper 可以做小数股。
      - A 股普通股票通常按 100 股一手买入，且 T+1。
      - 港股有不同 lot size，后续还要按具体股票处理。

    这些规则不应该散落在模型、回测、券商代码里。
    后续接 A 股 QMT/Ptrade 时，应该复用这里的 A 股规则。
    """

    market: str
    allow_fractional_shares: bool
    lot_size: int
    t_plus_one: bool
    allow_short: bool
    default_currency: str

    def round_target_shares(self, raw_shares: float, side: str) -> float:
        """把理论目标股数转换成该市场允许的股数。

        raw_shares:
          按目标金额 / 价格算出来的理论股数。

        side:
          buy / sell / hold。第一版主要处理 buy。

        规则：
          1. 允许小数股的市场直接保留 raw_shares。
          2. 不允许小数股的市场按 lot_size 向下取整，避免超买。
          3. 卖出时也按 lot_size 向下取整；A 股零股卖出规则后续再细化。
        """
        if raw_shares <= 0:
            return 0.0
        if self.allow_fractional_shares:
            return float(raw_shares)
        rounded_lots = math.floor(float(raw_shares) / self.lot_size)
        return float(rounded_lots * self.lot_size)


US_EQUITY_RULES = MarketRules(
    market="US",
    allow_fractional_shares=True,
    lot_size=1,
    t_plus_one=False,
    allow_short=False,
    default_currency="USD",
)


CHINA_A_RULES = MarketRules(
    market="CN_A",
    allow_fractional_shares=False,
    lot_size=100,
    t_plus_one=True,
    allow_short=False,
    default_currency="CNY",
)


HK_EQUITY_RULES = MarketRules(
    market="HK",
    allow_fractional_shares=False,
    lot_size=100,
    t_plus_one=False,
    allow_short=False,
    default_currency="HKD",
)


def market_rules_from_name(name: str | None) -> MarketRules:
    """根据配置名返回市场规则。

    当前支持：
      US / us_equity
      CN_A / china_a / a_share
      HK / hk_equity
    """
    normalized = (name or "US").strip().lower()
    if normalized in {"us", "us_equity", "alpaca"}:
        return US_EQUITY_RULES
    if normalized in {"cn_a", "china_a", "a_share", "ashare"}:
        return CHINA_A_RULES
    if normalized in {"hk", "hk_equity"}:
        return HK_EQUITY_RULES
    raise ValueError(f"Unknown market rules: {name}")
