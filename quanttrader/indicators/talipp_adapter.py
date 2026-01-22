"""talipp 指标适配器

使用 talipp 库提供 60+ 种技术指标的增量计算支持。
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Type

import talipp.indicators as ti
from talipp.ohlcv import OHLCV

from .incremental import BaseIncrementalIndicator, IndicatorBar, IndicatorRequirement


class TalippIndicator(BaseIncrementalIndicator):
    """通用 talipp 指标包装器

    将 talipp 指标封装为符合 BaseIncrementalIndicator 接口的类。

    Attributes:
        _warmup: 预热周期数
        _use_ohlcv: 是否使用 OHLCV 数据（而非仅 close）
        _value_extractor: 值提取函数，用于转换 talipp 的复合输出
        _indicator: talipp 指标实例
    """

    def __init__(
        self,
        requirement: IndicatorRequirement,
        indicator_class: Type,
        params: Dict[str, Any],
        warmup: int,
        use_ohlcv: bool = False,
        value_extractor: Optional[Callable[[Any], Any]] = None,
    ) -> None:
        """初始化 talipp 指标包装器

        Args:
            requirement: 指标需求配置
            indicator_class: talipp 指标类
            params: 指标参数
            warmup: 预热周期数
            use_ohlcv: 是否需要完整 OHLCV 数据
            value_extractor: 可选的值提取函数
        """
        super().__init__(requirement)
        self._warmup = warmup
        self._use_ohlcv = use_ohlcv
        self._value_extractor = value_extractor
        self._indicator = indicator_class(**params)

    @property
    def warmup_period(self) -> int:
        return self._warmup

    def _update(self, bar: IndicatorBar) -> None:
        if self._use_ohlcv:
            ohlcv = OHLCV(bar.open, bar.high, bar.low, bar.close, bar.volume)
            self._indicator.add(ohlcv)
        else:
            self._indicator.add(bar.close)

    def value(self) -> Any:
        if not self._indicator or len(self._indicator) == 0:
            return None
        raw = self._indicator[-1]
        if raw is None:
            return None
        if self._value_extractor:
            return self._value_extractor(raw)
        return raw


# 指标注册表
# 格式: type -> (class, params_builder, warmup_fn, use_ohlcv, value_extractor)
# - class: talipp 指标类
# - params_builder: 从 requirement.params 构建 talipp 参数的函数
# - warmup_fn: 计算预热周期的函数
# - use_ohlcv: 是否需要完整 OHLCV 数据
# - value_extractor: 可选的值提取函数，用于转换复合输出

TALIPP_REGISTRY: Dict[str, tuple] = {
    # === 移动平均 ===
    "sma": (
        ti.SMA,
        lambda p: {"period": p.get("period", 20)},
        lambda p: p.get("period", 20),
        False,
        None,
    ),
    "ema": (
        ti.EMA,
        lambda p: {"period": p.get("period", 20)},
        lambda p: p.get("period", 20),
        False,
        None,
    ),
    "dema": (
        ti.DEMA,
        lambda p: {"period": p.get("period", 20)},
        lambda p: p.get("period", 20) * 2,
        False,
        None,
    ),
    "tema": (
        ti.TEMA,
        lambda p: {"period": p.get("period", 20)},
        lambda p: p.get("period", 20) * 3,
        False,
        None,
    ),
    "wma": (
        ti.WMA,
        lambda p: {"period": p.get("period", 20)},
        lambda p: p.get("period", 20),
        False,
        None,
    ),
    "smma": (
        ti.SMMA,
        lambda p: {"period": p.get("period", 20)},
        lambda p: p.get("period", 20),
        False,
        None,
    ),
    "hma": (
        ti.HMA,
        lambda p: {"period": p.get("period", 20)},
        lambda p: p.get("period", 20),
        False,
        None,
    ),
    "kama": (
        ti.KAMA,
        lambda p: {
            "period": p.get("period", 10),
            "fast_ema_constant_period": p.get("fast", 2),
            "slow_ema_constant_period": p.get("slow", 30),
        },
        lambda p: p.get("period", 10),
        False,
        None,
    ),
    "zlema": (
        ti.ZLEMA,
        lambda p: {"period": p.get("period", 20)},
        lambda p: p.get("period", 20),
        False,
        None,
    ),
    "t3": (
        ti.T3,
        lambda p: {"period": p.get("period", 5), "factor": p.get("factor", 0.7)},
        lambda p: p.get("period", 5) * 6,
        False,
        None,
    ),
    "alma": (
        ti.ALMA,
        lambda p: {
            "period": p.get("period", 9),
            "offset": p.get("offset", 0.85),
            "sigma": p.get("sigma", 6),
        },
        lambda p: p.get("period", 9),
        False,
        None,
    ),
    "vwma": (
        ti.VWMA,
        lambda p: {"period": p.get("period", 20)},
        lambda p: p.get("period", 20),
        True,
        None,
    ),
    # === 动量指标 ===
    "rsi": (
        ti.RSI,
        lambda p: {"period": p.get("period", 14)},
        lambda p: p.get("period", 14) + 1,
        False,
        None,
    ),
    "macd": (
        ti.MACD,
        lambda p: {
            "fast_period": p.get("fast", 12),
            "slow_period": p.get("slow", 26),
            "signal_period": p.get("signal", 9),
        },
        lambda p: p.get("slow", 26) + p.get("signal", 9),
        False,
        lambda v: {
            "fast_line": v.macd,
            "signal_line": v.signal,
            "histogram": v.histogram,
            "macd": v.histogram,
            "diff": v.macd,
            "dea": v.signal,
        }
        if v
        else None,
    ),
    "stoch": (
        ti.Stoch,
        lambda p: {
            "period": p.get("period", 14),
            "smoothing_period": p.get("smoothing", 3),
        },
        lambda p: p.get("period", 14) + p.get("smoothing", 3),
        True,
        lambda v: {"k": v.k, "d": v.d} if v else None,
    ),
    "stochrsi": (
        ti.StochRSI,
        lambda p: {
            "rsi_period": p.get("rsi_period", p.get("period", 14)),
            "stoch_period": p.get("stoch_period", p.get("period", 14)),
            "k_smoothing_period": p.get("k_smoothing", 3),
            "d_smoothing_period": p.get("d_smoothing", 3),
        },
        lambda p: p.get("rsi_period", p.get("period", 14)) * 2,
        False,
        lambda v: {"k": v.k, "d": v.d} if v else None,
    ),
    "cci": (
        ti.CCI,
        lambda p: {"period": p.get("period", 20)},
        lambda p: p.get("period", 20),
        True,
        None,
    ),
    "roc": (
        ti.ROC,
        lambda p: {"period": p.get("period", 12)},
        lambda p: p.get("period", 12) + 1,
        False,
        None,
    ),
    "willr": (
        ti.Williams,
        lambda p: {"period": p.get("period", 14)},
        lambda p: p.get("period", 14),
        True,
        None,
    ),
    "williams": (
        ti.Williams,
        lambda p: {"period": p.get("period", 14)},
        lambda p: p.get("period", 14),
        True,
        None,
    ),
    "tsi": (
        ti.TSI,
        lambda p: {"fast_period": p.get("fast", 13), "slow_period": p.get("slow", 25)},
        lambda p: p.get("slow", 25) + p.get("fast", 13),
        False,
        None,
    ),
    "ao": (
        ti.AO,
        lambda p: {"fast_period": p.get("fast", 5), "slow_period": p.get("slow", 34)},
        lambda p: p.get("slow", 34),
        True,
        None,
    ),
    # === 波动率指标 ===
    "boll": (
        ti.BB,
        lambda p: {
            "period": p.get("period", 20),
            "std_dev_multiplier": p.get("std_dev", 2.0),
        },
        lambda p: p.get("period", 20),
        False,
        lambda v: {
            "upper": v.ub,
            "middle": v.cb,
            "lower": v.lb,
            "bandwidth": v.ub - v.lb if v else 0,
        }
        if v
        else None,
    ),
    "bb": (
        ti.BB,
        lambda p: {
            "period": p.get("period", 20),
            "std_dev_multiplier": p.get("std_dev", 2.0),
        },
        lambda p: p.get("period", 20),
        False,
        lambda v: {
            "upper": v.ub,
            "middle": v.cb,
            "lower": v.lb,
            "bandwidth": v.ub - v.lb if v else 0,
        }
        if v
        else None,
    ),
    "bollinger": (
        ti.BB,
        lambda p: {
            "period": p.get("period", 20),
            "std_dev_multiplier": p.get("std_dev", 2.0),
        },
        lambda p: p.get("period", 20),
        False,
        lambda v: {
            "upper": v.ub,
            "middle": v.cb,
            "lower": v.lb,
            "bandwidth": v.ub - v.lb if v else 0,
        }
        if v
        else None,
    ),
    "atr": (
        ti.ATR,
        lambda p: {"period": p.get("period", 14)},
        lambda p: p.get("period", 14),
        True,
        None,
    ),
    "natr": (
        ti.NATR,
        lambda p: {"period": p.get("period", 14)},
        lambda p: p.get("period", 14),
        True,
        None,
    ),
    "kc": (
        ti.KeltnerChannels,
        lambda p: {
            "ma_period": p.get("period", 20),
            "atr_period": p.get("atr_period", 10),
            "atr_mult_up": p.get("multiplier", 2.0),
            "atr_mult_down": p.get("multiplier", 2.0),
        },
        lambda p: max(p.get("period", 20), p.get("atr_period", 10)),
        True,
        lambda v: {"upper": v.ub, "middle": v.cb, "lower": v.lb} if v else None,
    ),
    "dc": (
        ti.DonchianChannels,
        lambda p: {"period": p.get("period", 20)},
        lambda p: p.get("period", 20),
        True,
        lambda v: {"upper": v.ub, "middle": v.cb, "lower": v.lb} if v else None,
    ),
    "stddev": (
        ti.StdDev,
        lambda p: {"period": p.get("period", 20)},
        lambda p: p.get("period", 20),
        False,
        None,
    ),
    # === 趋势指标 ===
    "adx": (
        ti.ADX,
        lambda p: {
            "di_period": p.get("di_period", p.get("period", 14)),
            "adx_period": p.get("adx_period", p.get("period", 14)),
        },
        lambda p: p.get("di_period", p.get("period", 14)) * 2,
        True,
        lambda v: {"adx": v.adx, "plus_di": v.plus_di, "minus_di": v.minus_di}
        if v
        else None,
    ),
    "aroon": (
        ti.Aroon,
        lambda p: {"period": p.get("period", 25)},
        lambda p: p.get("period", 25),
        True,
        lambda v: {"up": v.up, "down": v.down} if v else None,
    ),
    "psar": (
        ti.ParabolicSAR,
        lambda p: {
            "init_accel_factor": p.get("af", 0.02),
            "accel_factor_inc": p.get("af_inc", 0.02),
            "max_accel_factor": p.get("max_af", 0.2),
        },
        lambda p: 2,
        True,
        None,
    ),
    "supertrend": (
        ti.SuperTrend,
        lambda p: {
            "atr_period": p.get("period", 10),
            "mult": p.get("multiplier", 3.0),
        },
        lambda p: p.get("period", 10),
        True,
        lambda v: {"supertrend": v.value, "trend": v.trend.value if v.trend else None}
        if v
        else None,
    ),
    # === 成交量指标 ===
    "obv": (
        ti.OBV,
        lambda p: {},
        lambda p: 1,
        True,
        None,
    ),
    "vwap": (
        ti.VWAP,
        lambda p: {},
        lambda p: 1,
        True,
        None,
    ),
    "adl": (
        ti.AccuDist,
        lambda p: {},
        lambda p: 1,
        True,
        None,
    ),
    "accudist": (
        ti.AccuDist,
        lambda p: {},
        lambda p: 1,
        True,
        None,
    ),
    "chaikin": (
        ti.ChaikinOsc,
        lambda p: {"fast_period": p.get("fast", 3), "slow_period": p.get("slow", 10)},
        lambda p: p.get("slow", 10),
        True,
        None,
    ),
    # === 其他指标 ===
    "ichimoku": (
        ti.Ichimoku,
        lambda p: {
            "tenkan_period": p.get("tenkan", 9),
            "kijun_period": p.get("kijun", 26),
            "senkou_slow_period": p.get("senkou", 52),
            "chikou_lag_period": p.get("chikou_lag", 26),
            "senkou_lookup_period": p.get("senkou_lookup", 26),
        },
        lambda p: p.get("senkou", 52),
        True,
        lambda v: {
            "tenkan": v.conversion_line,
            "kijun": v.base_line,
            "senkou_a": v.cloud_leading_fast_line,
            "senkou_b": v.cloud_leading_slow_line,
            "chikou": v.lagging_line,
        }
        if v
        else None,
    ),
    "trix": (
        ti.TRIX,
        lambda p: {"period": p.get("period", 15)},
        lambda p: p.get("period", 15) * 3,
        False,
        None,
    ),
    "dpo": (
        ti.DPO,
        lambda p: {"period": p.get("period", 20)},
        lambda p: p.get("period", 20),
        False,
        None,
    ),
    "kst": (
        ti.KST,
        lambda p: {
            "roc1_period": p.get("roc1_period", 10),
            "roc1_ma_period": p.get("roc1_ma_period", 10),
            "roc2_period": p.get("roc2_period", 15),
            "roc2_ma_period": p.get("roc2_ma_period", 10),
            "roc3_period": p.get("roc3_period", 20),
            "roc3_ma_period": p.get("roc3_ma_period", 10),
            "roc4_period": p.get("roc4_period", 30),
            "roc4_ma_period": p.get("roc4_ma_period", 15),
            "signal_period": p.get("signal_period", 9),
        },
        lambda p: 55,
        False,
        lambda v: {"kst": v.kst, "signal": v.signal} if v else None,
    ),
    "uo": (
        ti.UO,
        lambda p: {
            "fast_period": p.get("fast", 7),
            "mid_period": p.get("mid", 14),
            "slow_period": p.get("slow", 28),
        },
        lambda p: p.get("slow", 28),
        True,
        None,
    ),
    # === 额外指标 ===
    "bop": (
        ti.BOP,
        lambda p: {},
        lambda p: 1,
        True,
        None,
    ),
    "chop": (
        ti.CHOP,
        lambda p: {"period": p.get("period", 14)},
        lambda p: p.get("period", 14),
        True,
        None,
    ),
    "emv": (
        ti.EMV,
        lambda p: {"period": p.get("period", 14)},
        lambda p: p.get("period", 14),
        True,
        None,
    ),
    "force": (
        ti.ForceIndex,
        lambda p: {"period": p.get("period", 13)},
        lambda p: p.get("period", 13),
        True,
        None,
    ),
    "mass": (
        ti.MassIndex,
        lambda p: {
            "ema_period": p.get("ema_period", 9),
            "sum_period": p.get("sum_period", 25),
        },
        lambda p: p.get("sum_period", 25),
        True,
        None,
    ),
    "vtx": (
        ti.VTX,
        lambda p: {"period": p.get("period", 14)},
        lambda p: p.get("period", 14),
        True,
        lambda v: {"plus_vtx": v.plus_vtx, "minus_vtx": v.minus_vtx} if v else None,
    ),
}


def get_supported_indicators() -> list[str]:
    """获取所有支持的指标类型列表"""
    return list(TALIPP_REGISTRY.keys())


def is_indicator_supported(indicator_type: str) -> bool:
    """检查指标类型是否受支持"""
    return indicator_type.lower() in TALIPP_REGISTRY


__all__ = [
    "TalippIndicator",
    "TALIPP_REGISTRY",
    "get_supported_indicators",
    "is_indicator_supported",
]
