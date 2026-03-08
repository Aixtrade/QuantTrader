from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Tuple

from xqtrader.accounts.base import BaseAccount, TradeResult
from xqtrader.strategies.base import StrategySignal


class BaseTrader(ABC):
    """交易器基类"""

    @abstractmethod
    async def execute_trade(
        self,
        signal: StrategySignal,
        price: float,
        account: BaseAccount,
        config: Any,
    ) -> Tuple[TradeResult, Any]:
        raise NotImplementedError
