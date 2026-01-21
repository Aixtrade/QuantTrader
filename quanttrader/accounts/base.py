from __future__ import annotations

from abc import ABC, abstractmethod


class BaseAccount(ABC):
    """账户基类"""

    def __init__(self, initial_capital: float):
        self._balance = float(initial_capital)

    @property
    def balance(self) -> float:
        """可用余额"""
        return self._balance

    @abstractmethod
    def apply_trade_result(self, trade_result: "TradeResult") -> "TradeResult":
        """根据交易结果更新资金"""
        raise NotImplementedError


class TradeResult:
    """交易结果占位"""

    def __init__(self, pnl: float = 0.0, fees: float = 0.0):
        self.pnl = pnl
        self.fees = fees
        self.balance_after = 0.0
