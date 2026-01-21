# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

QuantTrader 是一个量化交易引擎工具包，支持策略开发、回测、模拟盘和实盘交易。当前处于 MVP v0 阶段（单标的回测闭环）。

## 常用命令

```bash
# 安装依赖（使用 uv）
uv sync --dev

# 运行测试
uv run pytest

# 运行单个测试
uv run pytest tests/test_xxx.py -v

# 运行示例
uv run python examples/simple_backtest.py

# 运行主程序
uv run python main.py
```

## 架构概览

```
quanttrader/
├── strategies/     # 策略系统 - BaseStrategy 基类和动态加载器
├── engine/         # 执行引擎 - BacktestEngine (回测) / RealtimeEngine (实时)
├── accounts/       # 账户管理 - SimulatedAccount / FuturesSimulatedAccount
├── traders/        # 交易器 - EventsTrader (事件合约) / FuturesTrader (永续合约)
├── data/           # 数据服务 - DataCenterService + CCXT 适配器
│   └── adapters/   # 交易所适配器 - CCXTAdapter / BinanceAdapter
├── risk/           # 风控系统 - RiskManager (分级风控: WARNING/CRITICAL)
├── reports/        # 报告生成 - BacktestReport / TradeRecord / EquityPoint
├── config/         # 配置管理
└── utils/          # 工具函数
```

### 核心数据流

1. **DataCenterService** 获取市场数据 (OHLCV)
2. **BacktestEngine** 构建 `StrategyContext` 传入策略
3. **BaseStrategy.execute()** 返回 `StrategyResult` (含 signals)
4. **Trader** 执行交易信号，更新 **Account** 余额
5. **RiskManager** 检查风控规则
6. 生成 **BacktestReport**

### 关键类型

- `StrategySignal.action`: `BUY/SELL/HOLD` (通用) 或 `LONG/SHORT/CLOSE_LONG/CLOSE_SHORT/CLOSE` (永续合约)
- `PositionSide`: `LONG/SHORT` (双向持仓)
- `ExecutionMode`: `BACKTEST/PAPER/LIVE`
- `RiskLevel`: `NORMAL/WARNING/CRITICAL`

## 开发约定

### 策略开发

继承 `BaseStrategy` 并实现 `execute(context: StrategyContext) -> StrategyResult`:

```python
class MyStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name="my_strategy", version="1.0.0")

    def execute(self, context: StrategyContext) -> StrategyResult:
        # context.market_data["close"][-1] 获取最新收盘价
        # context.indicators 获取预计算指标
        signal = self.create_signal("LONG", context.symbol, confidence=0.8)
        return StrategyResult(signals=[signal], indicators={}, metadata={}, execution_time=0.0, success=True)
```

### 永续合约交易

- 使用 `FuturesSimulatedAccount` + `HedgePositionManager` (双向持仓)
- 保证金通过 `lock_margin/release_margin` 管理
- 盈亏计算: 多仓 `(exit - entry) * size`，空仓 `(entry - exit) * size`

### 风控规则

- 日亏损警告阈值: 3.5%，强平阈值: 5%
- 最大回撤警告阈值: 10%，强平阈值: 15%

### 数据中心使用

基于 CCXT 实现，支持 100+ 交易所：

```python
from quanttrader.data import DataCenterService, MarketDataRequest, MarketType

# 现货数据
async with DataCenterService(market_type=MarketType.SPOT) as dc:
    data = await dc.get_market_data(MarketDataRequest(symbol="BTC/USDT", interval="1h"))
    ticker = await dc.get_ticker("BTC/USDT")

# 永续合约
async with DataCenterService(market_type=MarketType.FUTURES) as dc:
    data = await dc.get_market_data(MarketDataRequest(symbol="BTC/USDT", interval="1h"))
```

特性：LRU 缓存 + 熔断器保护。Binance 合约额外支持 `fetch_mark_price_klines()` 和 `fetch_current_funding_rate()`。

## 路线图参考

详见 `docs/trading_system_roadmap.md` 和 `docs/trading_system_core_requirements.md`。
