"""技术指标计算模块

基于 talipp 库提供 60+ 种技术指标的增量计算支持。
"""

from quanttrader.indicators.incremental import (
    BaseIncrementalIndicator,
    IndicatorBar,
    IndicatorEngine,
    IndicatorRequirement,
)
from quanttrader.indicators.resampler import (
    OhlcvResampler,
    calculate_resample_ratio,
    needs_resampling,
)
from quanttrader.indicators.talipp_adapter import (
    TALIPP_REGISTRY,
    TalippIndicator,
    get_supported_indicators,
    is_indicator_supported,
)

__all__ = [
    # Core classes
    "IndicatorBar",
    "IndicatorEngine",
    "IndicatorRequirement",
    "BaseIncrementalIndicator",
    # Talipp adapter
    "TalippIndicator",
    "TALIPP_REGISTRY",
    "get_supported_indicators",
    "is_indicator_supported",
    # Resampler
    "OhlcvResampler",
    "calculate_resample_ratio",
    "needs_resampling",
]
