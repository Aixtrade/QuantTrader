---
name: create-strategy
description: 创建 XQTrader 量化交易策略文件。当用户要求创建新策略、编写策略模板、实现交易信号逻辑时使用此技能。
argument-hint: [策略名称，如 rsi_reversal]
---

# 创建 XQTrader 交易策略

你正在为 XQTrader 量化交易引擎创建策略文件。严格遵循以下规范。

前置条件：用户已安装 `pip install xqtrader[cli]`。

## 策略文件结构

在当前目录创建策略文件：

```
<strategy_name>.py    # 策略实现
```

## 完整策略模板

```python
"""
<策略中文名称> - <一句话描述>

策略逻辑：
  - <核心逻辑要点1>
  - <核心逻辑要点2>

适用场景：<震荡行情/趋势行情/...>
推荐时间框架：<1h/4h/...>
"""

import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Dict, Optional

from xqtrader.strategies.base import (
    BaseStrategy,
    StrategyContext,
    StrategyDataRequirements,
    StrategyResult,
)


@dataclass
class MyStrategyConfig:
    """策略参数配置"""

    # 指标参数
    period: int = 14
    timeframe: str = "1h"

    # 信号阈值
    upper_threshold: float = 70.0
    lower_threshold: float = 30.0


class MyStrategy(BaseStrategy):
    """策略类名使用 PascalCase，继承 BaseStrategy"""

    def __init__(
        self,
        name: str = "my_strategy",  # 策略ID，snake_case
        config: Optional[MyStrategyConfig] = None,
    ) -> None:
        super().__init__(
            name=name,
            version="1.0.0",
            description="策略中文描述",
            tags=["trend", "momentum"],
        )
        self.config = config or MyStrategyConfig()
        self._indicator_id = f"rsi_{self.config.timeframe}"
        self._history: deque = deque(maxlen=10)

    def get_config(self) -> Dict[str, Any]:
        """返回策略配置，用于日志和报告"""
        return {
            "period": self.config.period,
            "timeframe": self.config.timeframe,
            "upper_threshold": self.config.upper_threshold,
            "lower_threshold": self.config.lower_threshold,
        }

    def get_data_requirements(
        self, interval: str, config: Optional[Dict[str, Any]] = None
    ) -> StrategyDataRequirements:
        """声明数据需求"""
        min_bars = self.config.period + 10
        return StrategyDataRequirements(
            min_bars=min_bars,
            warmup_periods=min_bars,
        )

    def get_indicator_requirements(self) -> Dict[str, Dict[str, Any]]:
        """声明指标需求 - 引擎自动计算增量指标"""
        return {
            self._indicator_id: {
                "type": "rsi",
                "timeframe": self.config.timeframe,
                "period": self.config.period,
            }
        }

    def execute(self, context: StrategyContext) -> StrategyResult:
        """策略执行入口 - 每根K线调用一次"""
        start_time = time.time()

        # ── 第1步：获取增量指标 ──
        incremental = context.incremental_indicators or {}
        by_timeframe = incremental.get("by_timeframe", {})
        tf_state = by_timeframe.get(self.config.timeframe, {})
        is_warmed_up = tf_state.get(
            "is_warmed_up", incremental.get("is_warmed_up", False)
        )

        # ── 第2步：预热未完成时返回 HOLD ──
        if not is_warmed_up:
            return StrategyResult(
                signals=[self.create_signal("HOLD", context.symbol, reason="指标预热中")],
                indicators={},
                metadata={"status": "warmup"},
                execution_time=time.time() - start_time,
                success=True,
            )

        # ── 第3步：提取指标值 ──
        indicator_data = incremental.get("rsi", {}).get(self._indicator_id)
        if indicator_data is None:
            return StrategyResult(
                signals=[self.create_signal("HOLD", context.symbol, reason="指标数据缺失")],
                indicators={},
                metadata={"status": "no_data"},
                execution_time=time.time() - start_time,
                success=True,
            )

        current_value = indicator_data.get("rsi")
        self._history.append(current_value)

        if len(self._history) < 2:
            return StrategyResult(
                signals=[self.create_signal("HOLD", context.symbol, reason="历史数据不足")],
                indicators={"rsi": current_value},
                metadata={"status": "collecting"},
                execution_time=time.time() - start_time,
                success=True,
            )

        # ── 第4步：核心信号逻辑 ──
        prev_value = self._history[-2]
        current_price = context.market_data["close"][-1]

        action = "HOLD"
        reason = "no_signal"
        confidence = 0.5

        if prev_value >= self.config.upper_threshold and current_value < self.config.upper_threshold:
            action = "SHORT"
            reason = "overbought_reversal"
            confidence = min(0.5 + (prev_value - self.config.upper_threshold) / 100, 1.0)
        elif prev_value <= self.config.lower_threshold and current_value > self.config.lower_threshold:
            action = "LONG"
            reason = "oversold_reversal"
            confidence = min(0.5 + (self.config.lower_threshold - prev_value) / 100, 1.0)

        signal = self.create_signal(
            action=action,
            symbol=context.symbol,
            confidence=confidence,
            reason=reason,
        )

        return StrategyResult(
            signals=[signal],
            indicators={"rsi": float(current_value)},
            metadata={"price": current_price, "prev_rsi": float(prev_value)},
            execution_time=time.time() - start_time,
            success=True,
        )
```

## 创建后验证

策略文件创建后，使用 CLI 校验：

```bash
xqt strategy validate <strategy_name>.py
```

## 核心规范

### 信号类型

| 合约类型 | 开仓 | 平仓 | 观望 |
|---------|------|------|------|
| 永续合约 | `LONG` / `SHORT` | `CLOSE_LONG` / `CLOSE_SHORT` / `CLOSE` | `HOLD` |
| 事件合约 | `UP` / `DOWN` | N/A | `HOLD` |

### market_data 字段

`timestamps`, `open`, `high`, `low`, `close`, `volume`

```python
context.market_data["close"][-1]      # 最新收盘价
context.market_data["close"][-10:]    # 最近10根
```

### incremental_indicators 访问

```python
incremental = context.incremental_indicators or {}

# 按时间框架检查预热状态（推荐）
tf_state = incremental.get("by_timeframe", {}).get("1h", {})
is_warmed_up = tf_state.get("is_warmed_up", False)

# 获取指标值
rsi_data = incremental.get("rsi", {}).get("rsi_1h")
macd_data = incremental.get("macd", {}).get("macd_1h")
```

### 支持的指标类型

| 类别 | 类型 | 关键参数 |
|------|------|---------|
| 移动平均 | `sma`, `ema`, `dema`, `tema`, `wma`, `hma`, `kama`, `zlema` | `period` |
| 动量 | `rsi`, `macd`, `stoch`, `stochrsi`, `cci`, `roc`, `willr`, `tsi`, `ao` | `period` / `fast,slow,signal` |
| 波动率 | `boll`/`bb`, `atr`, `natr`, `kc`, `dc`, `stddev` | `period`, `std_dev` |
| 趋势 | `adx`, `aroon`, `psar`, `supertrend` | `period` |
| 成交量 | `obv`, `vwap`, `adl`, `chaikin` | `period` |

### MACD 指标字段

```python
macd_data["fast_line"]     # MACD 线
macd_data["signal_line"]   # 信号线
macd_data["histogram"]     # 柱状图
```

### 预热周期计算

| 指标 | 预热公式 | 示例 |
|------|---------|------|
| SMA/EMA | `period` | SMA(20) → 20 |
| RSI | `period + 1` | RSI(14) → 15 |
| MACD | `slow + signal` | MACD(12,26,9) → 35 |
| BB | `period` | BB(20) → 20 |
| ATR | `period` | ATR(14) → 14 |

`min_bars` 和 `warmup_periods` = 预热周期 + 安全余量（通常 +10）

### create_signal 参数

```python
self.create_signal(
    action="LONG",           # 必须：信号类型
    symbol=context.symbol,   # 必须：交易对
    quantity=0.0,            # 可选：数量（0=由引擎决定）
    price=None,              # 可选：限价
    stop_loss=None,          # 可选：止损价
    take_profit=None,        # 可选：止盈价
    confidence=0.8,          # 可选：置信度 0-1
    reason="golden_cross",   # 可选：原因描述
)
```

### StrategyResult 必填字段

```python
StrategyResult(
    signals=[signal],           # 信号列表（至少一个）
    indicators={...},           # 当前指标快照
    metadata={...},             # 诊断元数据
    execution_time=elapsed,     # 执行耗时（秒）
    success=True,               # 是否成功
    error_message=None,         # 仅失败时填写
)
```

## 设计检查清单

- [ ] 继承 `BaseStrategy`，实现 `execute()` 方法
- [ ] 使用 `@dataclass` 定义策略配置类
- [ ] 实现 `get_config()` 返回配置字典
- [ ] 实现 `get_data_requirements()` 声明数据需求
- [ ] 实现 `get_indicator_requirements()` 声明指标需求
- [ ] `execute()` 中首先检查预热状态
- [ ] 预热未完成时返回 `HOLD` 信号
- [ ] 指标数据缺失时优雅降级为 `HOLD`
- [ ] `confidence` 基于指标强度动态计算（0-1）
- [ ] `reason` 字段描述信号产生原因
- [ ] `execution_time` 正确计算并返回
