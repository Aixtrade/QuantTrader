from __future__ import annotations

import math
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional


@dataclass
class IndicatorRequirement:
    id: str
    type: str
    timeframe: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IndicatorBar:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    timeframe: str


class BaseIncrementalIndicator(ABC):
    def __init__(self, requirement: IndicatorRequirement) -> None:
        self.requirement = requirement
        self._bar_count = 0
        self._last_bar_ts: Optional[int] = None

    @property
    def bar_count(self) -> int:
        return self._bar_count

    @property
    def last_bar_ts(self) -> Optional[int]:
        return self._last_bar_ts

    @property
    @abstractmethod
    def warmup_period(self) -> int:
        raise NotImplementedError

    @property
    def is_warmed_up(self) -> bool:
        return self._bar_count >= self.warmup_period

    def update(self, bar: IndicatorBar) -> None:
        self._bar_count += 1
        self._last_bar_ts = bar.timestamp
        self._update(bar)

    @abstractmethod
    def _update(self, bar: IndicatorBar) -> None:
        raise NotImplementedError

    @abstractmethod
    def value(self) -> Any:
        raise NotImplementedError


class EMAIndicator(BaseIncrementalIndicator):
    def __init__(self, requirement: IndicatorRequirement) -> None:
        super().__init__(requirement)
        self.period = int(requirement.params.get("period", 0))
        if self.period <= 0:
            raise ValueError("EMA period must be positive")
        self.alpha = 2.0 / (self.period + 1.0)
        self._ema: Optional[float] = None
        self._seed_sum = 0.0

    @property
    def warmup_period(self) -> int:
        return self.period

    def _update(self, bar: IndicatorBar) -> None:
        close = bar.close
        if self._ema is None:
            self._seed_sum += close
            if self.bar_count == self.period:
                self._ema = self._seed_sum / self.period
            return
        self._ema = (close - self._ema) * self.alpha + self._ema

    def value(self) -> Optional[float]:
        return self._ema if self.is_warmed_up else None


class RSIIndicator(BaseIncrementalIndicator):
    def __init__(self, requirement: IndicatorRequirement) -> None:
        super().__init__(requirement)
        self.period = int(requirement.params.get("period", 0))
        if self.period <= 0:
            raise ValueError("RSI period must be positive")
        self._prev_close: Optional[float] = None
        self._avg_gain: Optional[float] = None
        self._avg_loss: Optional[float] = None
        self._gain_sum = 0.0
        self._loss_sum = 0.0
        self._change_count = 0

    @property
    def warmup_period(self) -> int:
        return self.period + 1

    @property
    def is_warmed_up(self) -> bool:
        return self._avg_gain is not None and self._avg_loss is not None

    def _update(self, bar: IndicatorBar) -> None:
        close = bar.close
        if self._prev_close is None:
            self._prev_close = close
            return

        change = close - self._prev_close
        gain = max(change, 0.0)
        loss = max(-change, 0.0)
        self._prev_close = close
        self._change_count += 1

        if self._avg_gain is None or self._avg_loss is None:
            self._gain_sum += gain
            self._loss_sum += loss
            if self._change_count >= self.period:
                self._avg_gain = self._gain_sum / self.period
                self._avg_loss = self._loss_sum / self.period
            return

        self._avg_gain = (self._avg_gain * (self.period - 1) + gain) / self.period
        self._avg_loss = (self._avg_loss * (self.period - 1) + loss) / self.period

    def value(self) -> Optional[float]:
        if not self.is_warmed_up:
            return None
        if self._avg_loss == 0:
            return 100.0
        rs = self._avg_gain / self._avg_loss if self._avg_loss else 0.0
        return 100.0 - (100.0 / (1.0 + rs))


class _EMAState:
    def __init__(self, period: int) -> None:
        if period <= 0:
            raise ValueError("EMA period must be positive")
        self.period = period
        self.alpha = 2.0 / (period + 1.0)
        self._value: Optional[float] = None
        self._seed_sum = 0.0
        self._count = 0

    @property
    def is_ready(self) -> bool:
        return self._value is not None

    @property
    def value(self) -> Optional[float]:
        return self._value

    def update(self, price: float) -> None:
        self._count += 1
        if self._value is None:
            self._seed_sum += price
            if self._count == self.period:
                self._value = self._seed_sum / self.period
            return
        self._value = (price - self._value) * self.alpha + self._value


class MACDIndicator(BaseIncrementalIndicator):
    def __init__(self, requirement: IndicatorRequirement) -> None:
        super().__init__(requirement)
        fast_period = int(requirement.params.get("fast", 12))
        slow_period = int(requirement.params.get("slow", 26))
        signal_period = int(requirement.params.get("signal", 9))
        if fast_period <= 0 or slow_period <= 0 or signal_period <= 0:
            raise ValueError("MACD periods must be positive")
        if fast_period >= slow_period:
            raise ValueError("MACD fast period must be smaller than slow period")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        self._fast = _EMAState(fast_period)
        self._slow = _EMAState(slow_period)
        self._signal = _EMAState(signal_period)
        self._diff: Optional[float] = None
        self._macd: Optional[float] = None

    @property
    def warmup_period(self) -> int:
        return self.slow_period + self.signal_period

    @property
    def is_warmed_up(self) -> bool:
        return self._signal.is_ready

    def _update(self, bar: IndicatorBar) -> None:
        close = bar.close
        self._fast.update(close)
        self._slow.update(close)
        if not (self._fast.is_ready and self._slow.is_ready):
            return
        diff = (self._fast.value or 0.0) - (self._slow.value or 0.0)
        self._diff = diff
        self._signal.update(diff)
        if self._signal.is_ready:
            self._macd = diff - (self._signal.value or 0.0)

    def value(self) -> Dict[str, Optional[float]]:
        return {
            "ema_fast": self._fast.value if self._fast.is_ready else None,
            "ema_slow": self._slow.value if self._slow.is_ready else None,
            "diff": self._diff if self._fast.is_ready and self._slow.is_ready else None,
            "dea": self._signal.value if self._signal.is_ready else None,
            "macd": self._macd if self._signal.is_ready else None,
            "fast_line": self._diff if self._fast.is_ready and self._slow.is_ready else None,
            "signal_line": self._signal.value if self._signal.is_ready else None,
            "histogram": self._macd if self._signal.is_ready else None,
        }


class BollingerIndicator(BaseIncrementalIndicator):
    def __init__(self, requirement: IndicatorRequirement) -> None:
        super().__init__(requirement)
        self.period = int(requirement.params.get("period", 0))
        if self.period <= 0:
            raise ValueError("Bollinger period must be positive")
        self.std_dev = float(requirement.params.get("std_dev", 2.0))
        self._window: Deque[float] = deque(maxlen=self.period)
        self._sum = 0.0
        self._sum_sq = 0.0

    @property
    def warmup_period(self) -> int:
        return self.period

    def _update(self, bar: IndicatorBar) -> None:
        close = bar.close
        if len(self._window) == self.period:
            removed = self._window.popleft()
            self._sum -= removed
            self._sum_sq -= removed * removed
        self._window.append(close)
        self._sum += close
        self._sum_sq += close * close

    def value(self) -> Dict[str, Optional[float]]:
        if len(self._window) < self.period:
            return {
                "upper": None,
                "middle": None,
                "lower": None,
                "bandwidth": None,
            }
        mean = self._sum / self.period
        variance = max(self._sum_sq / self.period - mean * mean, 0.0)
        std = math.sqrt(variance)
        upper = mean + self.std_dev * std
        lower = mean - self.std_dev * std
        return {
            "upper": upper,
            "middle": mean,
            "lower": lower,
            "bandwidth": upper - lower,
        }


class IndicatorEngine:
    def __init__(self) -> None:
        self._requirements: Dict[str, IndicatorRequirement] = {}
        self._indicators: Dict[str, BaseIncrementalIndicator] = {}
        self._last_update_ts: Optional[int] = None
        self._last_bar_ts_by_timeframe: Dict[str, int] = {}

    def register_requirements(self, requirements: Dict[str, Dict[str, Any]]) -> None:
        for req_id, spec in requirements.items():
            indicator_type = str(spec.get("type", "")).lower()
            timeframe = str(spec.get("timeframe", "")).lower()
            if not indicator_type or not timeframe:
                raise ValueError("indicator type and timeframe are required")
            params = {
                key: value for key, value in spec.items() if key not in {"type", "timeframe"}
            }
            requirement = IndicatorRequirement(
                id=req_id,
                type=indicator_type,
                timeframe=timeframe,
                params=params,
            )
            self._requirements[req_id] = requirement
            self._indicators[req_id] = self._build_indicator(requirement)

    def reset(self) -> None:
        self._requirements.clear()
        self._indicators.clear()
        self._last_update_ts = None
        self._last_bar_ts_by_timeframe.clear()

    def update(self, bar: IndicatorBar) -> None:
        updated = False
        for indicator in self._indicators.values():
            if indicator.requirement.timeframe != bar.timeframe:
                continue
            indicator.update(bar)
            updated = True
        if updated:
            self._last_update_ts = int(time.time() * 1000)
            self._last_bar_ts_by_timeframe[bar.timeframe] = bar.timestamp

    def warmup_from_ohlcv(self, ohlcv: Dict[str, List[float]], timeframe: str) -> None:
        closes = ohlcv.get("close", [])
        if not closes:
            return
        opens = ohlcv.get("open", [])
        highs = ohlcv.get("high", [])
        lows = ohlcv.get("low", [])
        volumes = ohlcv.get("volume", [])
        timestamps = ohlcv.get("timestamps", [])

        for idx, close in enumerate(closes):
            bar = IndicatorBar(
                timestamp=int(timestamps[idx]) if idx < len(timestamps) else 0,
                open=opens[idx] if idx < len(opens) else close,
                high=highs[idx] if idx < len(highs) else close,
                low=lows[idx] if idx < len(lows) else close,
                close=close,
                volume=volumes[idx] if idx < len(volumes) else 0.0,
                timeframe=timeframe,
            )
            self.update(bar)

    def snapshot(self) -> Dict[str, Any]:
        by_type: Dict[str, Dict[str, Any]] = {}
        by_timeframe: Dict[str, Dict[str, Any]] = {}

        overall_warmup = True
        for req_id, indicator in self._indicators.items():
            indicator_type = indicator.requirement.type
            timeframe = indicator.requirement.timeframe
            value = indicator.value()

            by_type.setdefault(indicator_type, {})[req_id] = value
            by_timeframe.setdefault(timeframe, {}).setdefault(indicator_type, {})[req_id] = value

            if not indicator.is_warmed_up:
                overall_warmup = False

        for timeframe, bucket in by_timeframe.items():
            warmup_state = all(
                indicator.is_warmed_up
                for indicator in self._indicators.values()
                if indicator.requirement.timeframe == timeframe
            )
            bucket["is_warmed_up"] = warmup_state
            bucket["bar_close_ts"] = self._last_bar_ts_by_timeframe.get(timeframe)

        snapshot = dict(by_type)
        snapshot["is_warmed_up"] = overall_warmup
        snapshot["timestamp"] = self._last_update_ts
        snapshot["bar_close_ts"] = (
            max(self._last_bar_ts_by_timeframe.values())
            if self._last_bar_ts_by_timeframe
            else None
        )
        snapshot["by_timeframe"] = by_timeframe
        return snapshot

    def _build_indicator(self, requirement: IndicatorRequirement) -> BaseIncrementalIndicator:
        indicator_type = requirement.type
        if indicator_type == "ema":
            return EMAIndicator(requirement)
        if indicator_type == "rsi":
            return RSIIndicator(requirement)
        if indicator_type == "macd":
            return MACDIndicator(requirement)
        if indicator_type in {"boll", "bollinger", "bb"}:
            return BollingerIndicator(requirement)
        raise ValueError(f"unsupported indicator type: {indicator_type}")


__all__ = [
    "IndicatorRequirement",
    "IndicatorBar",
    "IndicatorEngine",
    "EMAIndicator",
    "RSIIndicator",
    "MACDIndicator",
    "BollingerIndicator",
]
