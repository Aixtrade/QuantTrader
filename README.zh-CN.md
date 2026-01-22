# QuantTrader

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[English](README.md)

一个量化交易引擎工具包，支持策略开发、回测、模拟盘和实盘交易。

---

## 功能特性

- **策略框架**: 模块化策略系统，支持热重载
- **多交易所支持**: 通过 CCXT 支持 100+ 交易所
- **技术指标**: 基于 talipp 的 60+ 技术指标
- **合约交易**: 永续合约双向持仓模式
- **事件合约**: 二元期权风格交易
- **风控系统**: 分级风控机制 (WARNING/CRITICAL)
- **智能缓存**: LRU + TTL 缓存及熔断保护

---

## 安装

### 环境要求

- Python >= 3.11
- [uv](https://github.com/astral-sh/uv) (推荐) 或 pip

### 安装步骤

```bash
# 克隆仓库
git clone https://github.com/yourusername/QuantTrader.git
cd QuantTrader

# 使用 uv 安装依赖
uv sync --dev

# 或使用 pip
pip install -e ".[dev]"
```

---

## 快速开始

### 1. 创建策略

```python
from quanttrader.strategies.base import (
    BaseStrategy,
    StrategyContext,
    StrategyResult,
)

class MyStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name="my_strategy", version="1.0.0")

    def execute(self, context: StrategyContext) -> StrategyResult:
        close_prices = context.market_data.get("close", [])
        if not close_prices:
            return StrategyResult(
                signals=[self.create_signal("HOLD", context.symbol)],
                indicators={},
                metadata={},
                execution_time=0.0,
                success=True,
            )

        # 在此实现交易逻辑
        signal = self.create_signal("LONG", context.symbol, confidence=0.8)
        return StrategyResult(
            signals=[signal],
            indicators={},
            metadata={},
            execution_time=0.0,
            success=True,
        )
```

### 2. 运行回测

```python
import asyncio
from datetime import datetime, timedelta, timezone
from quanttrader.engine.backtest import BacktestConfig, BacktestEngine

async def main():
    strategy = MyStrategy()
    engine = BacktestEngine()

    now = datetime.now(timezone.utc)
    config = BacktestConfig(
        symbol="BTC/USDT",
        interval="1h",
        initial_capital=10000.0,
        start_time=int((now - timedelta(days=7)).timestamp() * 1000),
        end_time=int(now.timestamp() * 1000),
    )

    async for event in engine.run(strategy, config):
        if event.event_type == "trade":
            print(f"交易: {event.data}")
        elif event.event_type == "complete":
            print(f"最终余额: {event.data.get('final_balance')}")

asyncio.run(main())
```

---

## 信号约定

| 合约类型 | 信号 |
|---------|------|
| 永续/期货 | `LONG`, `SHORT`, `CLOSE_LONG`, `CLOSE_SHORT`, `CLOSE` |
| 事件合约 | `UP`, `DOWN`, `HOLD` |

> 事件合约交易器兼容 `LONG`/`SHORT`/`BUY`/`SELL` 并自动映射到 `UP`/`DOWN`。

---

## 架构

```
quanttrader/
├── strategies/     # 策略系统 - BaseStrategy 基类和动态加载器
├── engine/         # 执行引擎 - 回测引擎 / 实时引擎
├── accounts/       # 账户管理 - 模拟账户 / 合约模拟账户
├── traders/        # 交易器 - 事件交易器 / 合约交易器
├── data/           # 数据服务 - 数据中心 + CCXT 适配器
│   └── adapters/   # 交易所适配器 - CCXTAdapter / BinanceAdapter
├── indicators/     # 技术指标 - 基于 talipp 的 60+ 指标
├── risk/           # 风控系统 - 分级风控管理器
├── reports/        # 报告生成 - 回测报告 / 交易记录
└── config/         # 配置管理
```

### 数据流

```
市场数据 (OHLCV) → 指标引擎 → 策略上下文 → 策略执行
     ↓                                        ↓
DataCenterService                      StrategyResult
                                              ↓
账户更新 ← 交易执行 ← 风控检查 ← 交易信号
     ↓
回测报告
```

---

## 示例

查看 [`examples/`](examples/) 目录获取完整示例：

- **MACD 策略**: `examples/macd_strategy/`
  - `macd_strategy.py` - 策略实现
  - `run_backtest_futures.py` - 合约回测
  - `run_backtest_events.py` - 事件合约回测

---

## 开发

```bash
# 运行所有测试
uv run pytest

# 运行特定测试文件
uv run pytest tests/test_data_center.py -v

# 运行特定测试类
uv run pytest tests/test_data_center.py::TestLRUCache -v

# 运行示例
uv run python examples/macd_strategy/run_backtest_futures.py
```

---

## 风控规则

| 规则 | 警告 | 强平 |
|-----|------|-----|
| 日亏损 | 3.5% | 5% |
| 最大回撤 | 10% | 15% |

---

## 路线图

- [x] **MVP v0**: 单标的回测闭环
- [ ] **MVP v1**: 实时纸交易
- [ ] **MVP v2**: 资金费率优化
- [ ] **MVP v3**: 多资产组合
- [ ] **MVP v4**: 实盘接口

详见 [`docs/trading_system_roadmap.md`](docs/trading_system_roadmap.md)。

---

## 依赖

| 包 | 用途 |
|---|------|
| [ccxt](https://github.com/ccxt/ccxt) | 交易所连接 |
| [talipp](https://github.com/nardew/talipp) | 技术指标 |
| [numpy](https://numpy.org/) | 数值计算 |
| [pydantic](https://pydantic.dev/) | 数据验证 |
| [httpx](https://www.python-httpx.org/) | 异步 HTTP 客户端 |

---

## 许可证

MIT License - 详见 [LICENSE](LICENSE)。

---

## 贡献

欢迎贡献代码！请阅读 [AGENTS.md](AGENTS.md) 了解编码规范。
