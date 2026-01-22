# QuantTrader

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[中文文档](README.zh-CN.md)

A quantitative trading engine toolkit for strategy development, backtesting, paper trading, and live trading.

---

## Features

- **Strategy Framework**: Modular strategy system with hot-reload support
- **Multi-Exchange Support**: 100+ exchanges via CCXT
- **Technical Indicators**: 60+ indicators powered by talipp
- **Futures Trading**: Perpetual futures with hedge mode
- **Event Contracts**: Binary options style trading
- **Risk Management**: Multi-level risk control (WARNING/CRITICAL)
- **Smart Caching**: LRU + TTL caching with circuit breaker

---

## Installation

### Requirements

- Python >= 3.11
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Install

```bash
# Clone the repository
git clone https://github.com/yourusername/QuantTrader.git
cd QuantTrader

# Install dependencies with uv
uv sync --dev

# Or with pip
pip install -e ".[dev]"
```

---

## Quick Start

### 1. Create a Strategy

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

        # Your trading logic here
        signal = self.create_signal("LONG", context.symbol, confidence=0.8)
        return StrategyResult(
            signals=[signal],
            indicators={},
            metadata={},
            execution_time=0.0,
            success=True,
        )
```

### 2. Run Backtest

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
            print(f"Trade: {event.data}")
        elif event.event_type == "complete":
            print(f"Final balance: {event.data.get('final_balance')}")

asyncio.run(main())
```

---

## Signal Conventions

| Contract Type | Signals |
|--------------|---------|
| Perpetual/Futures | `LONG`, `SHORT`, `CLOSE_LONG`, `CLOSE_SHORT`, `CLOSE` |
| Event Contracts | `UP`, `DOWN`, `HOLD` |

> Event trader also accepts `LONG`/`SHORT`/`BUY`/`SELL` and auto-maps to `UP`/`DOWN`.

---

## Architecture

```
quanttrader/
├── strategies/     # Strategy system - BaseStrategy and dynamic loader
├── engine/         # Execution engines - BacktestEngine / RealtimeEngine
├── accounts/       # Account management - SimulatedAccount / FuturesSimulatedAccount
├── traders/        # Trade executors - EventsTrader / FuturesTrader
├── data/           # Data services - DataCenterService + CCXT adapters
│   └── adapters/   # Exchange adapters - CCXTAdapter / BinanceAdapter
├── indicators/     # Technical indicators - 60+ indicators via talipp
├── risk/           # Risk management - RiskManager (WARNING/CRITICAL levels)
├── reports/        # Report generation - BacktestReport / TradeRecord
└── config/         # Configuration management
```

### Data Flow

```
Market Data (OHLCV) → Indicator Engine → Strategy Context → Strategy Execution
     ↓                                                            ↓
DataCenterService                                          StrategyResult
                                                                  ↓
Account Update ← Trade Execution ← Risk Check ← Trading Signals
     ↓
BacktestReport
```

---

## Examples

See the [`examples/`](examples/) directory for complete examples:

- **MACD Strategy**: `examples/macd_strategy/`
  - `macd_strategy.py` - Strategy implementation
  - `run_backtest_futures.py` - Futures backtest
  - `run_backtest_events.py` - Event contracts backtest

---

## Development

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_data_center.py -v

# Run specific test class
uv run pytest tests/test_data_center.py::TestLRUCache -v

# Run examples
uv run python examples/macd_strategy/run_backtest_futures.py
```

---

## Risk Rules

| Rule | Warning | Critical |
|------|---------|----------|
| Daily Loss | 3.5% | 5% |
| Max Drawdown | 10% | 15% |

---

## Roadmap

- [x] **MVP v0**: Single-asset backtesting
- [ ] **MVP v1**: Real-time paper trading
- [ ] **MVP v2**: Funding rate optimization
- [ ] **MVP v3**: Multi-asset portfolio
- [ ] **MVP v4**: Live trading interface

See [`docs/trading_system_roadmap.md`](docs/trading_system_roadmap.md) for details.

---

## Dependencies

| Package | Purpose |
|---------|---------|
| [ccxt](https://github.com/ccxt/ccxt) | Exchange connectivity |
| [talipp](https://github.com/nardew/talipp) | Technical indicators |
| [numpy](https://numpy.org/) | Numerical computing |
| [pydantic](https://pydantic.dev/) | Data validation |
| [httpx](https://www.python-httpx.org/) | Async HTTP client |

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Contributing

Contributions are welcome! Please read the [AGENTS.md](AGENTS.md) for coding conventions.
