from __future__ import annotations

from dataclasses import dataclass

from .base import BaseAccount, TradeResult


@dataclass
class SimulatedAccount(BaseAccount):
    """简单模拟账户 - 用于事件合约回测"""

    def __init__(self, initial_capital: float):
        super().__init__(initial_capital)

    def apply_trade_result(self, trade_result: TradeResult) -> TradeResult:
        self._balance += trade_result.pnl
        trade_result.balance_after = self._balance
        return trade_result
