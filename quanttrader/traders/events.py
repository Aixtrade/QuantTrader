from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from quanttrader.accounts.base import BaseAccount, TradeResult
from quanttrader.traders.base import BaseTrader
from quanttrader.strategies.base import StrategySignal


@dataclass
class EventsBacktestConfig:
    symbol: str
    interval: str
    investment_amount: float
    payout_multiplier: float = 1.8
    start_time: int | None = None
    end_time: int | None = None


class EventsTrader(BaseTrader):
    DEFAULT_PAYOUT_MULTIPLIER = 1.8

    def _normalize_action(self, action: str) -> str:
        action_upper = action.upper()
        if action_upper in {"UP", "DOWN", "HOLD"}:
            return action_upper
        if action_upper in {"LONG", "BUY"}:
            return "UP"
        if action_upper in {"SHORT", "SELL"}:
            return "DOWN"
        return action_upper

    async def execute_trade(
        self,
        signal: StrategySignal,
        price: float,
        account: BaseAccount,
        config: EventsBacktestConfig,
    ) -> Tuple[TradeResult, dict]:
        normalized_action = self._normalize_action(signal.action)
        if normalized_action not in {"UP", "DOWN", "HOLD"}:
            normalized_action = "HOLD"

        if normalized_action == "HOLD":
            result = TradeResult()
            record = {
                "symbol": config.symbol,
                "action": normalized_action,
                "entry_price": price,
                "payout_multiplier": config.payout_multiplier,
                "win": None,
                "skipped": True,
            }
            return result, record

        invest = signal.quantity or config.investment_amount
        payout_multiplier = config.payout_multiplier or self.DEFAULT_PAYOUT_MULTIPLIER
        # 简化：胜负由信号 action 决定（UP 视为看涨，DOWN 视为看跌）
        win = normalized_action == "UP"
        pnl = invest * (payout_multiplier - 1) if win else -invest
        result = TradeResult(pnl=pnl, fees=0.0)
        account.apply_trade_result(result)
        record = {
            "symbol": config.symbol,
            "action": normalized_action,
            "entry_price": price,
            "payout_multiplier": payout_multiplier,
            "win": win,
        }
        return result, record
