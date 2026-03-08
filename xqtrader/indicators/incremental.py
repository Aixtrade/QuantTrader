"""增量指标计算引擎

基于 talipp 库提供 60+ 种技术指标的增量计算支持，支持多时间框架重采样。
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class IndicatorRequirement:
    """指标需求配置

    Attributes:
        id: 指标唯一标识符
        type: 指标类型 (如 "macd", "rsi", "boll")
        timeframe: 时间框架 (如 "1h", "15m")
        params: 指标参数
    """

    id: str
    type: str
    timeframe: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IndicatorBar:
    """K 线数据

    Attributes:
        timestamp: 时间戳 (毫秒)
        open: 开盘价
        high: 最高价
        low: 最低价
        close: 收盘价
        volume: 成交量
        timeframe: 时间框架
    """

    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    timeframe: str


class BaseIncrementalIndicator(ABC):
    """增量指标基类

    所有指标实现必须继承此类并实现抽象方法。
    """

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


class IndicatorEngine:
    """指标计算引擎

    管理多个指标的增量计算，支持多时间框架重采样。

    使用示例::

        engine = IndicatorEngine()
        engine.register_requirements({
            "macd_1h": {"type": "macd", "timeframe": "1h", "fast": 12, "slow": 26, "signal": 9},
            "rsi_15m": {"type": "rsi", "timeframe": "15m", "period": 14},
        }, source_timeframe="15m")

        for bar in bars:
            engine.update(bar)
            snapshot = engine.snapshot()
    """

    def __init__(self) -> None:
        self._requirements: Dict[str, IndicatorRequirement] = {}
        self._indicators: Dict[str, BaseIncrementalIndicator] = {}
        self._resamplers: Dict[str, Any] = {}  # OhlcvResampler by target timeframe
        self._source_timeframe: Optional[str] = None
        self._last_update_ts: Optional[int] = None
        self._last_bar_ts_by_timeframe: Dict[str, int] = {}

    def register_requirements(
        self,
        requirements: Dict[str, Dict[str, Any]],
        source_timeframe: Optional[str] = None,
    ) -> None:
        """注册指标需求

        Args:
            requirements: 指标配置字典，key 为指标 ID，value 为配置
            source_timeframe: 源数据时间框架（用于计算重采样比例）
        """
        from .resampler import OhlcvResampler, calculate_resample_ratio, needs_resampling

        self._source_timeframe = source_timeframe

        for req_id, spec in requirements.items():
            indicator_type = str(spec.get("type", "")).lower()
            timeframe = str(spec.get("timeframe", "")).lower()
            if not indicator_type or not timeframe:
                raise ValueError("indicator type and timeframe are required")

            params = {
                key: value
                for key, value in spec.items()
                if key not in {"type", "timeframe"}
            }
            requirement = IndicatorRequirement(
                id=req_id,
                type=indicator_type,
                timeframe=timeframe,
                params=params,
            )
            self._requirements[req_id] = requirement
            self._indicators[req_id] = self._build_indicator(requirement)

            # 设置重采样器（如果需要）
            target_tf = requirement.timeframe
            if source_timeframe and needs_resampling(source_timeframe, target_tf):
                if target_tf not in self._resamplers:
                    ratio = calculate_resample_ratio(source_timeframe, target_tf)
                    self._resamplers[target_tf] = OhlcvResampler(
                        source_tf=source_timeframe,
                        target_tf=target_tf,
                        ratio=ratio,
                    )

    def reset(self) -> None:
        """重置引擎状态"""
        self._requirements.clear()
        self._indicators.clear()
        self._resamplers.clear()
        self._source_timeframe = None
        self._last_update_ts = None
        self._last_bar_ts_by_timeframe.clear()

    def update(self, bar: IndicatorBar) -> None:
        """更新指标

        Args:
            bar: K 线数据
        """
        # 1. 更新与源 timeframe 匹配的指标
        for indicator in self._indicators.values():
            if indicator.requirement.timeframe == bar.timeframe:
                indicator.update(bar)

        # 2. 通过重采样器更新其他 timeframe 的指标
        for target_tf, resampler in self._resamplers.items():
            resampled = resampler.add(bar)
            if resampled:
                for indicator in self._indicators.values():
                    if indicator.requirement.timeframe == target_tf:
                        indicator.update(resampled)
                self._last_bar_ts_by_timeframe[target_tf] = resampled.timestamp

        self._last_update_ts = int(time.time() * 1000)
        self._last_bar_ts_by_timeframe[bar.timeframe] = bar.timestamp

    def warmup_from_ohlcv(self, ohlcv: Dict[str, List[float]], timeframe: str) -> None:
        """从 OHLCV 数据预热指标

        Args:
            ohlcv: OHLCV 数据字典
            timeframe: 时间框架
        """
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
        """获取当前指标快照

        Returns:
            包含所有指标值和元数据的字典
        """
        by_type: Dict[str, Dict[str, Any]] = {}
        by_timeframe: Dict[str, Dict[str, Any]] = {}

        overall_warmup = True
        for req_id, indicator in self._indicators.items():
            indicator_type = indicator.requirement.type
            timeframe = indicator.requirement.timeframe
            value = indicator.value()

            by_type.setdefault(indicator_type, {})[req_id] = value
            by_timeframe.setdefault(timeframe, {}).setdefault(indicator_type, {})[
                req_id
            ] = value

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

    def _build_indicator(
        self, requirement: IndicatorRequirement
    ) -> BaseIncrementalIndicator:
        """使用 talipp 构建指标

        Args:
            requirement: 指标需求配置

        Returns:
            指标实例

        Raises:
            ValueError: 当指标类型不支持时
        """
        from .talipp_adapter import TALIPP_REGISTRY, TalippIndicator

        indicator_type = requirement.type.lower()
        if indicator_type not in TALIPP_REGISTRY:
            supported = ", ".join(sorted(TALIPP_REGISTRY.keys()))
            raise ValueError(
                f"Unsupported indicator type: {indicator_type}. "
                f"Supported types: {supported}"
            )

        cls, params_fn, warmup_fn, use_ohlcv, value_extractor = TALIPP_REGISTRY[
            indicator_type
        ]
        params = params_fn(requirement.params)
        warmup = warmup_fn(requirement.params)

        return TalippIndicator(
            requirement=requirement,
            indicator_class=cls,
            params=params,
            warmup=warmup,
            use_ohlcv=use_ohlcv,
            value_extractor=value_extractor,
        )


__all__ = [
    "IndicatorRequirement",
    "IndicatorBar",
    "BaseIncrementalIndicator",
    "IndicatorEngine",
]
