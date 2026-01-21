# QuantTrader
完整的量化交易解决方案，涵盖策略开发、回测、模拟、实盘全流程

## 策略信号约定
- 永续/期货：使用 `LONG` / `SHORT` / `CLOSE_*` 表示开平仓方向。
- 事件合约：使用 `UP` / `DOWN` / `HOLD` 表示涨跌方向。
- 事件合约交易器兼容 `LONG` / `SHORT` / `BUY` / `SELL` 并自动映射到 `UP` / `DOWN`。
