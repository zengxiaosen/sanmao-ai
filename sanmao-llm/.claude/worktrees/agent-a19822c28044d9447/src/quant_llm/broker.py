"""券商适配层的兼容导出文件。

真正实现放在：
  quant_llm.brokers.alpaca
  quant_llm.brokers.common
  quant_llm.brokers.qmt
  quant_llm.brokers.futu

保留这个文件的原因：
  旧脚本已经从 quant_llm.broker import ...
  为了减少重构风险，这里继续导出旧名字。

以后新增券商时，不要把逻辑写进这个文件。
"""

from quant_llm.brokers.alpaca import AlpacaConfig, AlpacaTradingClient, alpaca_symbol
from quant_llm.brokers.common import (
    build_broker_order_plan,
    check_order_risk_limits,
    load_latest_paper_orders,
    reconcile_paper_portfolio_with_alpaca,
    submit_order_plan_to_alpaca,
)
from quant_llm.brokers.futu import FutuConfig, FutuTradingClient, check_futu_opend_environment
from quant_llm.brokers.qmt import QmtConfig, QmtTradingClient, check_qmt_environment

__all__ = [
    "AlpacaConfig",
    "AlpacaTradingClient",
    "FutuConfig",
    "FutuTradingClient",
    "QmtConfig",
    "QmtTradingClient",
    "alpaca_symbol",
    "build_broker_order_plan",
    "check_futu_opend_environment",
    "check_order_risk_limits",
    "check_qmt_environment",
    "load_latest_paper_orders",
    "reconcile_paper_portfolio_with_alpaca",
    "submit_order_plan_to_alpaca",
]
