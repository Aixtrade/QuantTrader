"""K 线时间框架重采样器

将低时间框架 K 线聚合到高时间框架，例如：4 根 15m K 线 -> 1 根 1h K 线
基于时间戳边界对齐，确保聚合结果与交易所原生 K 线一致。

设计原则：
1. 时间边界对齐 - 根据时间戳判断 K 线所属周期，而非简单计数
2. 即时输出 - 在目标周期最后一根源 K 线时立即输出，避免延迟
3. 增量计算 - 每根 K 线只处理一次，O(1) 复杂度
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .incremental import IndicatorBar


@dataclass
class OhlcvResampler:
    """将低时间框架 K 线聚合到高时间框架

    基于时间戳边界对齐，在目标周期最后一根源 K 线时即时输出。

    例如：2 根 30m K 线 → 1 根 1h K 线
    - 00:00 的 30m bar → 开始聚合（不输出）
    - 00:30 的 30m bar → 检测到是周期最后一根，立即输出 00:00 的 1h bar

    Attributes:
        source_tf: 源时间框架，如 "30m"
        target_tf: 目标时间框架，如 "1h"
        ratio: 聚合比例，如 2 (30m * 2 = 1h)
    """

    source_tf: str
    target_tf: str
    ratio: int

    _source_seconds_ms: int = field(default=0, init=False)
    _target_seconds_ms: int = field(default=0, init=False)
    _current_period_start: Optional[int] = field(default=None, init=False)
    _pending_open: Optional[float] = field(default=None, init=False)
    _pending_high: float = field(default=float("-inf"), init=False)
    _pending_low: float = field(default=float("inf"), init=False)
    _pending_close: float = field(default=0.0, init=False)
    _pending_volume: float = field(default=0.0, init=False)
    _pending_ts: int = field(default=0, init=False)
    _count: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        """初始化时间框架的毫秒数"""
        self._source_seconds_ms = _tf_to_seconds(self.source_tf) * 1000
        self._target_seconds_ms = _tf_to_seconds(self.target_tf) * 1000

    def _get_period_start(self, timestamp_ms: int) -> int:
        """计算时间戳所属的目标时间框架周期起始时间

        Args:
            timestamp_ms: 毫秒时间戳

        Returns:
            周期起始时间（毫秒）
        """
        return (timestamp_ms // self._target_seconds_ms) * self._target_seconds_ms

    def _is_period_last_bar(self, bar_timestamp_ms: int) -> bool:
        """判断当前 bar 是否是目标周期的最后一根

        Args:
            bar_timestamp_ms: 当前 bar 的时间戳（毫秒）

        Returns:
            如果是周期最后一根返回 True
        """
        period_start = self._get_period_start(bar_timestamp_ms)
        period_end = period_start + self._target_seconds_ms
        next_bar_ts = bar_timestamp_ms + self._source_seconds_ms
        return next_bar_ts >= period_end

    def add(self, bar: IndicatorBar) -> Optional[IndicatorBar]:
        """添加一根源 K 线，返回聚合后的 K 线（如果完成）

        基于时间戳边界对齐，在目标周期最后一根源 K 线时即时输出。

        Args:
            bar: 源时间框架的 K 线数据

        Returns:
            聚合完成时返回目标时间框架的 K 线，否则返回 None
        """
        bar_period_start = self._get_period_start(bar.timestamp)
        result: Optional[IndicatorBar] = None

        # 检查是否进入新周期（处理数据跳跃的情况）
        if self._current_period_start is not None and bar_period_start != self._current_period_start:
            # 输出上一周期的聚合结果（如果有未输出的数据）
            if self._pending_open is not None:
                result = self._create_output_bar()
                self._reset()

        # 更新当前周期
        self._current_period_start = bar_period_start

        # 聚合当前 bar
        if self._pending_open is None:
            self._pending_open = bar.open
            self._pending_ts = bar_period_start  # 使用周期起始时间作为时间戳

        self._pending_high = max(self._pending_high, bar.high)
        self._pending_low = min(self._pending_low, bar.low)
        self._pending_close = bar.close
        self._pending_volume += bar.volume
        self._count += 1

        # 检查是否是目标周期的最后一根 bar，如果是则立即输出
        if self._is_period_last_bar(bar.timestamp):
            result = self._create_output_bar()
            self._reset()

        return result

    def _create_output_bar(self) -> Optional[IndicatorBar]:
        """创建输出的聚合 K 线"""
        if self._pending_open is None:
            return None
        return IndicatorBar(
            timestamp=self._pending_ts,
            open=self._pending_open,
            high=self._pending_high,
            low=self._pending_low,
            close=self._pending_close,
            volume=self._pending_volume,
            timeframe=self.target_tf,
        )

    def flush(self) -> Optional[IndicatorBar]:
        """强制输出当前未完成的聚合结果

        用于处理最后一批不完整的 K 线。

        Returns:
            如果有待处理数据则返回聚合结果，否则返回 None
        """
        result = self._create_output_bar()
        if result:
            self._reset()
        return result

    def _reset(self) -> None:
        """重置内部状态，准备下一个聚合周期"""
        self._current_period_start = None
        self._pending_open = None
        self._pending_high = float("-inf")
        self._pending_low = float("inf")
        self._pending_close = 0.0
        self._pending_volume = 0.0
        self._count = 0

    @property
    def pending_count(self) -> int:
        """当前待处理的 K 线数量"""
        return self._count

    @property
    def current_period_start(self) -> Optional[int]:
        """当前正在聚合的周期起始时间"""
        return self._current_period_start


def calculate_resample_ratio(source_tf: str, target_tf: str) -> int:
    """计算两个时间框架的比例

    Args:
        source_tf: 源时间框架，如 "15m"
        target_tf: 目标时间框架，如 "1h"

    Returns:
        比例值，如 4 (15m * 4 = 1h)

    Raises:
        ValueError: 当无法从源时间框架重采样到目标时间框架时
    """
    source_seconds = _tf_to_seconds(source_tf)
    target_seconds = _tf_to_seconds(target_tf)

    if target_seconds < source_seconds:
        raise ValueError(f"Cannot resample {source_tf} to smaller {target_tf}")
    if target_seconds % source_seconds != 0:
        raise ValueError(f"Cannot evenly resample {source_tf} to {target_tf}")

    return target_seconds // source_seconds


def _tf_to_seconds(tf: str) -> int:
    """时间框架转秒数

    支持的格式: 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w

    Args:
        tf: 时间框架字符串

    Returns:
        对应的秒数

    Raises:
        ValueError: 当时间框架格式不支持时
    """
    tf = tf.lower().strip()
    if not tf:
        raise ValueError("Empty timeframe")

    if tf.endswith("m"):
        return int(tf[:-1]) * 60
    if tf.endswith("h"):
        return int(tf[:-1]) * 3600
    if tf.endswith("d"):
        return int(tf[:-1]) * 86400
    if tf.endswith("w"):
        return int(tf[:-1]) * 7 * 86400

    raise ValueError(f"Unknown timeframe: {tf}")


def needs_resampling(source_tf: str, target_tf: str) -> bool:
    """判断是否需要重采样

    Args:
        source_tf: 源时间框架
        target_tf: 目标时间框架

    Returns:
        如果目标时间框架大于源时间框架，返回 True
    """
    try:
        source_seconds = _tf_to_seconds(source_tf)
        target_seconds = _tf_to_seconds(target_tf)
        return target_seconds > source_seconds
    except ValueError:
        return False


__all__ = [
    "OhlcvResampler",
    "calculate_resample_ratio",
    "needs_resampling",
]
