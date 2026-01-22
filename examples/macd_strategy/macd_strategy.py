"""MACD 策略

基于 MACD 金叉/死叉的简单趋势跟踪策略。

信号规则：
- 金叉（MACD 上穿信号线）：做多信号
- 死叉（MACD 下穿信号线）：做空信号
- 柱状图增强确认
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, Optional, Tuple


from quanttrader.strategies.base import (
    BaseStrategy,
    StrategyContext,
    StrategyDataRequirements,
    StrategyResult,
    StrategySignal,
)


@dataclass
class MACDConfig:
    """MACD 策略配置"""

    fast_period: int = 12  # 快线周期
    slow_period: int = 26  # 慢线周期
    signal_period: int = 9  # 信号线周期
    timeframe: str = "1h"
    min_histogram: float = 0.0  # 最小柱状图阈值（过滤弱信号）
    require_histogram_confirm: bool = True  # 是否需要柱状图确认


class MACDStrategy(BaseStrategy):
    """MACD 金叉死叉策略

    交易逻辑：
    1. 计算 MACD、信号线、柱状图
    2. 检测金叉（MACD 从下方穿过信号线）-> LONG
    3. 检测死叉（MACD 从上方穿过信号线）-> SHORT
    4. 可选：柱状图增强确认

    Example:
        strategy = MACDStrategy()
        result = strategy.execute(context)
    """

    def __init__(
        self,
        name: str = "macd_crossover",
        config: Optional[MACDConfig] = None,
    ) -> None:
        super().__init__(
            name=name,
            version="1.0.0",
            description="MACD 金叉死叉策略",
            tags=["trend", "macd", "crossover"],
        )
        self.config = config or MACDConfig()
        self._indicator_id = f"macd_{self.config.timeframe}"
        self._macd_history: Deque[Tuple[float, float, float]] = deque(maxlen=10)

    def get_config(self) -> Dict[str, Any]:
        return {
            "fast_period": self.config.fast_period,
            "slow_period": self.config.slow_period,
            "signal_period": self.config.signal_period,
            "timeframe": self.config.timeframe,
            "min_histogram": self.config.min_histogram,
            "require_histogram_confirm": self.config.require_histogram_confirm,
        }

    def get_data_requirements(
        self, interval: str, config: Optional[Dict[str, Any]] = None
    ) -> StrategyDataRequirements:
        # MACD 需要至少 slow_period + signal_period 根 K 线
        min_bars = self.config.slow_period + self.config.signal_period + 10
        return StrategyDataRequirements(
            min_bars=min_bars,
            warmup_periods=min_bars,
        )

    def get_indicator_requirements(self) -> Dict[str, Dict[str, Any]]:
        return {
            self._indicator_id: {
                "type": "macd",
                "timeframe": self.config.timeframe,
                "fast": self.config.fast_period,
                "slow": self.config.slow_period,
                "signal": self.config.signal_period,
            }
        }

    def execute(self, context: StrategyContext) -> StrategyResult:
        """执行策略"""
        import time

        start_time = time.time()

        # 优先使用增量指标
        incremental = context.incremental_indicators or {}
        macd_payload = incremental.get("macd", {}).get(self._indicator_id)
        timeframe_state = incremental.get("by_timeframe", {}).get(self.config.timeframe, {})
        is_warmed_up = timeframe_state.get("is_warmed_up", incremental.get("is_warmed_up", False))

        if macd_payload:
            current_macd = macd_payload.get("fast_line")
            current_signal = macd_payload.get("signal_line")
            current_histogram = macd_payload.get("histogram")

            if not is_warmed_up or current_macd is None or current_signal is None:
                return StrategyResult(
                    signals=[self.create_signal("HOLD", context.symbol, reason="MACD 计算中")],
                    indicators={
                        "macd": current_macd,
                        "signal": current_signal,
                        "histogram": current_histogram,
                    },
                    metadata={"status": "warmup"},
                    execution_time=time.time() - start_time,
                    success=True,
                )

            self._macd_history.append((current_macd, current_signal, current_histogram or 0.0))
            if len(self._macd_history) < 2:
                return StrategyResult(
                    signals=[self.create_signal("HOLD", context.symbol, reason="MACD 数据不足")],
                    indicators={
                        "macd": current_macd,
                        "signal": current_signal,
                        "histogram": current_histogram,
                    },
                    metadata={"status": "warmup"},
                    execution_time=time.time() - start_time,
                    success=True,
                )

            prev_macd, prev_signal, prev_histogram = self._macd_history[-2]

            indicators = {
                "macd": float(current_macd),
                "signal": float(current_signal),
                "histogram": float(current_histogram or 0.0),
                "prev_macd": float(prev_macd),
                "prev_signal": float(prev_signal),
                "prev_histogram": float(prev_histogram),
            }

            signal = self._detect_crossover(
                context.symbol,
                float(current_macd),
                float(current_signal),
                float(current_histogram or 0.0),
                float(prev_macd),
                float(prev_signal),
                float(prev_histogram),
            )

            return StrategyResult(
                signals=[signal],
                indicators=indicators,
                metadata={
                    "crossover_type": signal.reason,
                    "price": context.market_data.get("close", [0.0])[-1]
                    if context.market_data.get("close")
                    else 0.0,
                },
                execution_time=time.time() - start_time,
                success=True,
            )

        return StrategyResult(
            signals=[self.create_signal("HOLD", context.symbol, reason="缺少增量指标")],
            indicators={},
            metadata={"error": "incremental_indicators_required"},
            execution_time=time.time() - start_time,
            success=True,
        )

    def _detect_crossover(
        self,
        symbol: str,
        macd: float,
        signal: float,
        histogram: float,
        prev_macd: float,
        prev_signal: float,
        prev_histogram: float,
    ) -> StrategySignal:
        """检测 MACD 交叉信号"""

        # 金叉：MACD 从下方穿过信号线
        is_golden_cross = prev_macd <= prev_signal and macd > signal

        # 死叉：MACD 从上方穿过信号线
        is_death_cross = prev_macd >= prev_signal and macd < signal

        # 柱状图确认（可选）
        histogram_confirms_long = (
            not self.config.require_histogram_confirm
            or (histogram > self.config.min_histogram and histogram > prev_histogram)
        )

        histogram_confirms_short = (
            not self.config.require_histogram_confirm
            or (histogram < -self.config.min_histogram and histogram < prev_histogram)
        )

        if is_golden_cross and histogram_confirms_long:
            return self.create_signal(
                action="LONG",
                symbol=symbol,
                confidence=min(0.5 + abs(histogram) * 10, 1.0),  # 柱状图越大置信度越高
                reason="golden_cross",
            )

        if is_death_cross and histogram_confirms_short:
            return self.create_signal(
                action="SHORT",
                symbol=symbol,
                confidence=min(0.5 + abs(histogram) * 10, 1.0),
                reason="death_cross",
            )

        # 无交叉，持有
        return self.create_signal(
            action="HOLD",
            symbol=symbol,
            confidence=0.5,
            reason="no_crossover",
        )
