from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, AsyncGenerator, Dict, Optional

from quanttrader.strategies.base import BaseStrategy, StrategyContext, StrategyResult


class ExecutionMode(str, Enum):
    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE = "live"


@dataclass
class ExecutionEvent:
    event_type: str  # tick, trade, progress, complete, error
    data: Dict[str, Any]
    timestamp: datetime


@dataclass
class ExecutionConfig:
    symbol: str
    interval: str
    start_time: Optional[int] = None
    end_time: Optional[int] = None


class BaseEngine(ABC):
    def __init__(self, mode: ExecutionMode) -> None:
        self.mode = mode

    @abstractmethod
    async def run(
        self,
        strategy: BaseStrategy,
        config: ExecutionConfig,
        progress_callback: Optional[Any] = None,
    ) -> AsyncGenerator[ExecutionEvent, None]:
        if False:
            yield ExecutionEvent(event_type="noop", data={}, timestamp=datetime.utcnow())
        raise NotImplementedError

    async def _emit(
        self, event_type: str, data: Dict[str, Any]
    ) -> ExecutionEvent:
        return ExecutionEvent(event_type=event_type, data=data, timestamp=datetime.utcnow())


__all__ = [
    "ExecutionMode",
    "ExecutionEvent",
    "ExecutionConfig",
    "BaseEngine",
]
