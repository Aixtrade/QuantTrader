# XQTrader 开发指南

本文档面向开发者，涵盖项目架构、开发环境搭建和贡献指引。

---

## 开发安装

### 环境要求

- Python >= 3.12
- [uv](https://github.com/astral-sh/uv) (推荐) 或 pip

### 从源码安装

```bash
git clone https://github.com/Aixtrade/QuantTrader.git
cd XQTrader

# 使用 uv 安装依赖
uv sync --group dev

# 或使用 pip
pip install -e ".[dev]"
```

---

## 架构概览

```
xqtrader/
├── strategies/     # 策略系统 - BaseStrategy 基类和动态加载器
├── engine/         # 执行引擎 - BacktestEngine / RealtimeEngine
├── accounts/       # 账户管理 - SimulatedAccount / FuturesSimulatedAccount
├── traders/        # 交易器 - EventsTrader / FuturesTrader
├── data/           # 数据服务 - DataCenterService + CCXT 适配器
│   └── adapters/   # 交易所适配器 - CCXTAdapter / BinanceAdapter
├── indicators/     # 技术指标 - 基于 talipp 的 60+ 指标
├── risk/           # 风控系统 - RiskManager (WARNING/CRITICAL 分级)
├── reports/        # 报告生成 - BacktestReport / TradeRecord
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

### 关键类型

- `StrategySignal.action`: `BUY/SELL/HOLD` (通用) 或 `LONG/SHORT/CLOSE_LONG/CLOSE_SHORT/CLOSE` (永续合约)
- `PositionSide`: `LONG/SHORT` (双向持仓)
- `ExecutionMode`: `BACKTEST/PAPER/LIVE`
- `RiskLevel`: `NORMAL/WARNING/CRITICAL`

---

## 策略开发

继承 `BaseStrategy` 并实现 `execute(context: StrategyContext) -> StrategyResult`：

```python
from xqtrader.strategies.base import (
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

        signal = self.create_signal("LONG", context.symbol, confidence=0.8)
        return StrategyResult(
            signals=[signal],
            indicators={},
            metadata={},
            execution_time=0.0,
            success=True,
        )
```

### 信号约定

| 合约类型 | 信号 |
|---------|------|
| 永续/期货 | `LONG`, `SHORT`, `CLOSE_LONG`, `CLOSE_SHORT`, `CLOSE` |
| 事件合约 | `UP`, `DOWN`, `HOLD` |

> 事件合约交易器兼容 `LONG`/`SHORT`/`BUY`/`SELL` 并自动映射到 `UP`/`DOWN`。

### 永续合约交易

- 使用 `FuturesSimulatedAccount` + `HedgePositionManager` (双向持仓)
- 保证金通过 `lock_margin/release_margin` 管理
- 盈亏计算: 多仓 `(exit - entry) * size`，空仓 `(entry - exit) * size`

### 数据中心

基于 CCXT 实现，支持 100+ 交易所：

```python
from xqtrader.data import DataCenterService, MarketDataRequest, MarketType

# 现货数据
async with DataCenterService(market_type=MarketType.SPOT) as dc:
    data = await dc.get_market_data(MarketDataRequest(symbol="BTC/USDT", interval="1h"))
    ticker = await dc.get_ticker("BTC/USDT")

# 永续合约
async with DataCenterService(market_type=MarketType.FUTURES) as dc:
    data = await dc.get_market_data(MarketDataRequest(symbol="BTC/USDT", interval="1h"))
```

特性：LRU 缓存 + 熔断器保护。Binance 合约额外支持 `fetch_mark_price_klines()` 和 `fetch_current_funding_rate()`。

---

## 风控规则

| 规则 | 警告 | 强平 |
|-----|------|------|
| 日亏损 | 3.5% | 5% |
| 最大回撤 | 10% | 15% |

---

## 测试

```bash
# 运行所有测试
uv run pytest

# 运行特定测试文件
uv run pytest tests/test_data_center.py -v

# 运行特定测试类
uv run pytest tests/test_data_center.py::TestLRUCache -v
```

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

## 路线图

- [x] **MVP v0**: 单标的回测闭环
- [ ] **MVP v1**: 实时纸交易
- [ ] **MVP v2**: 资金费率优化
- [ ] **MVP v3**: 多资产组合
- [ ] **MVP v4**: 实盘接口

详见 [`trading_system_roadmap.md`](trading_system_roadmap.md)。

---

## 贡献

欢迎贡献代码！请阅读 [AGENTS.md](../AGENTS.md) 了解编码规范。
