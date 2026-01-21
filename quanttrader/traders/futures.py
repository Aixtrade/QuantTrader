from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from quanttrader.accounts.base import BaseAccount, TradeResult
from quanttrader.accounts.futures import FuturesSimulatedAccount, PositionSide
from quanttrader.traders.base import BaseTrader
from quanttrader.strategies.base import StrategySignal


@dataclass
class FuturesBacktestConfig:
    symbol: str
    interval: str
    leverage: int = 10
    position_size_pct: float = 0.1
    taker_fee: float = 0.0004
    maker_fee: float = 0.0002
    slippage: float = 0.0005
    maintenance_margin_ratio: float = 0.004
    funding_rate_interval: int = 28800
    start_time: int | None = None
    end_time: int | None = None


@dataclass
class FuturesPosition:
    symbol: str
    side: PositionSide
    entry_price: float
    size: float
    leverage: int
    margin: float
    entry_fee: float = 0.0
    liquidation_price: float = 0.0


class HedgePositionManager:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.long_position: FuturesPosition | None = None
        self.short_position: FuturesPosition | None = None

    def get_position(self, side: PositionSide) -> FuturesPosition | None:
        return self.long_position if side == PositionSide.LONG else self.short_position

    def set_position(self, position: FuturesPosition | None, side: PositionSide) -> None:
        if side == PositionSide.LONG:
            self.long_position = position
        else:
            self.short_position = position

    def has_position(self, side: PositionSide | None = None) -> bool:
        if side is None:
            return self.long_position is not None or self.short_position is not None
        return self.get_position(side) is not None

    def get_total_margin(self) -> float:
        margin = 0.0
        if self.long_position:
            margin += self.long_position.margin
        if self.short_position:
            margin += self.short_position.margin
        return margin


class FuturesTrader(BaseTrader):
    async def execute_trade(
        self,
        signal: StrategySignal,
        price: float,
        account: BaseAccount,
        config: FuturesBacktestConfig,
        position_manager: HedgePositionManager | None = None,
    ) -> Tuple[TradeResult, List[dict]]:
        if position_manager is None:
            position_manager = HedgePositionManager(config.symbol)
        if not isinstance(account, FuturesSimulatedAccount):
            raise TypeError("FuturesTrader requires FuturesSimulatedAccount")
        # 极简实现：仅支持开仓/平仓，未实现止盈止损
        action = signal.action.upper()
        side = PositionSide.LONG if action in {"LONG", "BUY", "OPEN_LONG"} else PositionSide.SHORT
        records: List[dict] = []

        if action in {"LONG", "BUY", "OPEN_LONG", "SHORT", "SELL", "OPEN_SHORT"}:
            margin = account.balance * config.position_size_pct
            nominal = margin * config.leverage
            trade_price = price * (1 + config.slippage)
            size = nominal / trade_price
            fee = trade_price * size * config.taker_fee
            account.lock_margin(margin, side)
            account.apply_fee(fee)
            pos = FuturesPosition(
                symbol=config.symbol,
                side=side,
                entry_price=trade_price,
                size=size,
                leverage=config.leverage,
                margin=margin,
                entry_fee=fee,
                liquidation_price=trade_price * (1 - config.maintenance_margin_ratio) if side == PositionSide.LONG else trade_price * (1 + config.maintenance_margin_ratio),
            )
            position_manager.set_position(pos, side)
            records.append({"action": action, "side": side.value, "price": trade_price, "size": size})
            result = TradeResult(pnl=-fee, fees=fee)
            account.apply_trade_result(result)
            return result, records

        if action in {"CLOSE_LONG", "CLOSE_SHORT", "CLOSE"}:
            sides = [PositionSide.LONG, PositionSide.SHORT] if action == "CLOSE" else [PositionSide.LONG if "LONG" in action else PositionSide.SHORT]
            total_pnl = 0.0
            total_fee = 0.0
            for s in sides:
                pos = position_manager.get_position(s)
                if not pos:
                    continue
                exit_price = price * (1 - config.slippage if s == PositionSide.LONG else 1 + config.slippage)
                realized = (exit_price - pos.entry_price) * pos.size if s == PositionSide.LONG else (pos.entry_price - exit_price) * pos.size
                fee = exit_price * pos.size * config.taker_fee
                pnl = realized - fee - pos.entry_fee
                account.release_margin(pos.margin, s)
                account.apply_fee(fee)
                total_pnl += pnl
                total_fee += fee
                records.append({"action": action, "side": s.value, "price": exit_price, "size": pos.size, "pnl": pnl})
                position_manager.set_position(None, s)
            result = TradeResult(pnl=total_pnl, fees=total_fee)
            account.apply_trade_result(result)
            return result, records

        return TradeResult(), records
