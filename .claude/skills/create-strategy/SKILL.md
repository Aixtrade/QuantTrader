---
name: create-strategy
description: 创建量化交易策略文件。当用户要求创建新策略、编写策略模板、实现交易信号逻辑时使用此技能。
argument-hint: [策略名称，如 rsi_reversal]
---

# 创建 XQTrader 交易策略

你正在为 XQTrader 量化交易引擎创建标准化的策略文件。严格遵循以下规范。

## 策略文件结构

每个策略应创建为独立目录，放在 `examples/` 下：

```
examples/<strategy_name>/
├── <strategy_name>.py          # 策略实现（必须）
├── run_backtest_futures.py     # 永续合约回测脚本（按需）
└── run_backtest_events.py      # 事件合约回测脚本（按需）
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
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from xqtrader.strategies.base import (
    BaseStrategy,
    StrategyContext,
    StrategyDataRequirements,
    StrategyResult,
    StrategySignal,
)


@dataclass
class MyStrategyConfig:
    """策略参数配置 - 使用 dataclass 便于管理和序列化"""

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
            tags=["trend", "momentum"],  # 分类标签
        )
        self.config = config or MyStrategyConfig()
        # 指标ID格式：{指标类型}_{时间框架}
        self._indicator_id = f"rsi_{self.config.timeframe}"
        # 使用 deque 保存历史值用于交叉检测
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
        """声明数据需求 - 引擎据此准备数据"""
        min_bars = self.config.period + 10  # 指标周期 + 安全余量
        return StrategyDataRequirements(
            min_bars=min_bars,
            warmup_periods=min_bars,
        )

    def get_indicator_requirements(self) -> Dict[str, Dict[str, Any]]:
        """声明指标需求 - 引擎自动计算增量指标"""
        return {
            self._indicator_id: {
                "type": "rsi",  # 指标类型（见下方支持列表）
                "timeframe": self.config.timeframe,
                "period": self.config.period,
            }
        }

    def execute(self, context: StrategyContext) -> StrategyResult:
        """
        策略执行入口 - 每根K线调用一次。

        Args:
            context: 包含市场数据、指标、账户信息的上下文

        Returns:
            StrategyResult: 包含信号、指标值、元数据的结果
        """
        start_time = time.time()

        # ── 第1步：获取增量指标 ──
        incremental = context.incremental_indicators or {}

        # 检查预热状态（优先按时间框架检查）
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

        # ── 第4步：需要足够历史才能判断 ──
        if len(self._history) < 2:
            return StrategyResult(
                signals=[self.create_signal("HOLD", context.symbol, reason="历史数据不足")],
                indicators={"rsi": current_value},
                metadata={"status": "collecting"},
                execution_time=time.time() - start_time,
                success=True,
            )

        # ── 第5步：核心信号逻辑 ──
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

        # ── 第6步：构建并返回结果 ──
        signal = self.create_signal(
            action=action,
            symbol=context.symbol,
            confidence=confidence,
            reason=reason,
        )

        return StrategyResult(
            signals=[signal],
            indicators={"rsi": float(current_value)},
            metadata={
                "price": current_price,
                "prev_rsi": float(prev_value),
            },
            execution_time=time.time() - start_time,
            success=True,
        )
```

## 回测脚本模板

```python
"""回测脚本 - 永续合约"""

import asyncio
from xqtrader.engine.backtest import BacktestEngine
from xqtrader.config.backtest_config import BacktestConfig
from <strategy_module> import MyStrategy, MyStrategyConfig


async def main():
    config = BacktestConfig(
        symbol="BTC/USDT",
        interval="1h",
        initial_capital=10000.0,
        contract_type="futures",  # "futures" 或 "events"
        start_date="2025-01-01",
        end_date="2025-03-01",
    )

    strategy = MyStrategy(config=MyStrategyConfig(period=14))
    engine = BacktestEngine()
    report = await engine.run(strategy, config)
    report.print_summary()


if __name__ == "__main__":
    asyncio.run(main())
```

## 核心规范（必须遵守）

### 信号类型

| 合约类型 | 开仓 | 平仓 | 观望 |
|---------|------|------|------|
| 永续合约 | `LONG` / `SHORT` | `CLOSE_LONG` / `CLOSE_SHORT` / `CLOSE` | `HOLD` |
| 事件合约 | `UP` / `DOWN` | N/A | `HOLD` |

- 优先使用 `LONG/SHORT/CLOSE_LONG/CLOSE_SHORT`，引擎会自动兼容映射
- `BUY` → `LONG`/`UP`，`SELL` → `SHORT`/`DOWN`

### market_data 访问

```python
context.market_data["close"][-1]     # 最新收盘价
context.market_data["close"][-10:]   # 最近10根K线收盘价
context.market_data["high"][-1]      # 最新最高价
context.market_data["volume"][-1]    # 最新成交量
context.market_data["timestamps"][-1]  # 最新时间戳（毫秒）
```

字段：`timestamps`, `open`, `high`, `low`, `close`, `volume`

### incremental_indicators 访问

```python
incremental = context.incremental_indicators or {}

# 全局预热状态
is_warmed_up = incremental.get("is_warmed_up", False)

# 按时间框架的预热状态（推荐）
tf_state = incremental.get("by_timeframe", {}).get("1h", {})
is_warmed_up = tf_state.get("is_warmed_up", False)

# 获取指标值（按类型和ID）
macd_data = incremental.get("macd", {}).get("macd_1h")
rsi_data = incremental.get("rsi", {}).get("rsi_1h")
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
macd_data = incremental.get("macd", {}).get("macd_1h")
macd_data["fast_line"]     # MACD 线（别名 "diff"）
macd_data["signal_line"]   # 信号线（别名 "dea"）
macd_data["histogram"]     # 柱状图（别名 "macd"）
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
    indicators={...},           # 当前指标快照（用于报告）
    metadata={...},             # 诊断元数据（任意 JSON）
    execution_time=elapsed,     # 执行耗时（秒，用 time.time() 计算）
    success=True,               # 执行是否成功
    error_message=None,         # 仅失败时填写
)
```

## 设计检查清单

创建策略时确认以下事项：

- [ ] 继承 `BaseStrategy`，实现 `execute()` 方法
- [ ] 使用 `@dataclass` 定义策略配置类
- [ ] 实现 `get_config()` 返回配置字典
- [ ] 实现 `get_data_requirements()` 声明数据需求
- [ ] 实现 `get_indicator_requirements()` 声明指标需求
- [ ] `execute()` 中首先检查预热状态
- [ ] 预热未完成时返回 `HOLD` 信号
- [ ] 指标数据缺失时优雅降级为 `HOLD`
- [ ] 使用 `deque` 保存历史值用于交叉检测
- [ ] `confidence` 基于指标强度动态计算（0-1）
- [ ] `reason` 字段描述信号产生原因
- [ ] `metadata` 包含当前价格等诊断信息
- [ ] `execution_time` 正确计算并返回

## 参考文件

- 策略基类：`xqtrader/strategies/base.py`
- MACD 策略示例：`examples/macd_strategy/macd_strategy.py`
- 回测引擎：`xqtrader/engine/backtest.py`
- 指标引擎：`xqtrader/indicators/incremental.py`
- 指标适配器：`xqtrader/indicators/talipp_adapter.py`
