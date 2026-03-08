from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .base import BaseAccount, TradeResult


class PositionSide(str, Enum):
    LONG = "long"
    SHORT = "short"


@dataclass
class FuturesSimulatedAccount(BaseAccount):
    """永续合约模拟账户 - 支持双向持仓"""

    def __init__(self, initial_capital: float):
        super().__init__(initial_capital)
        self._long_margin_locked = 0.0
        self._short_margin_locked = 0.0

    @property
    def margin_locked(self) -> float:
        return self._long_margin_locked + self._short_margin_locked

    @property
    def wallet_balance(self) -> float:
        return self._balance + self.margin_locked

    def lock_margin(self, amount: float, side: PositionSide):
        if amount > self._balance:
            raise ValueError("Insufficient funds")
        self._balance -= amount
        if side == PositionSide.LONG:
            self._long_margin_locked += amount
        else:
            self._short_margin_locked += amount

    def release_margin(self, amount: float, side: PositionSide):
        if side == PositionSide.LONG:
            self._long_margin_locked -= amount
        else:
            self._short_margin_locked -= amount
        self._balance += amount

    def apply_fee(self, fee: float):
        self._balance -= fee

    def apply_pnl(self, pnl: float):
        self._balance += pnl

    def apply_trade_result(self, trade_result: TradeResult) -> TradeResult:
        self._balance += trade_result.pnl
        trade_result.balance_after = self._balance
        return trade_result
