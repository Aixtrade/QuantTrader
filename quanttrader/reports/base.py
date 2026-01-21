from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List


@dataclass
class EquityPoint:
    timestamp: datetime
    equity: float
    drawdown: float
    drawdown_pct: float


@dataclass
class TradeRecord:
    trade_id: str
    symbol: str
    action: str
    entry_time: datetime
    entry_price: float
    exit_time: datetime | None = None
    exit_price: float | None = None
    quantity: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    fees: float = 0.0
    holding_period: timedelta | None = None


@dataclass
class BacktestReport:
    strategy_name: str
    symbol: str
    interval: str
    start_time: datetime
    end_time: datetime
    duration_days: int
    initial_capital: float
    final_capital: float
    total_return: float
    total_pnl: float
    total_trades: int
    win_rate: float
    max_drawdown_pct: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": {
                "strategy_name": self.strategy_name,
                "symbol": self.symbol,
                "interval": self.interval,
                "period": f"{self.start_time} - {self.end_time}",
                "duration_days": self.duration_days,
                "initial_capital": self.initial_capital,
                "final_capital": self.final_capital,
            },
            "returns": {
                "total_return": self.total_return,
                "total_pnl": self.total_pnl,
            },
            "trades": {
                "total": self.total_trades,
                "win_rate": self.win_rate,
            },
            "risk": {
                "max_drawdown_pct": self.max_drawdown_pct,
            },
        }
