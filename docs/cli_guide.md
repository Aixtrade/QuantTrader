# XQTrader CLI 使用指南

## 安装

```bash
# 仅核心库（用于在代码中导入使用）
pip install xqtrader

# 核心库 + CLI 命令行工具
pip install xqtrader[cli]

# 开发模式（从源码）
uv sync --dev
```

安装后提供两个等价命令：

- `xqtrader` — 完整命令名
- `xqt` — 简写别名

开发模式下使用 `uv run xqtrader` 或 `uv run xqt`。

## 全局选项

```bash
xqtrader --version    # 显示版本号
xqtrader --help       # 显示帮助信息
```

## 命令概览

| 命令 | 说明 |
|------|------|
| `xqtrader backtest` | 运行策略回测 |
| `xqtrader strategy list` | 列出目录下的策略 |
| `xqtrader strategy new` | 生成策略模板文件 |
| `xqtrader strategy validate` | 校验策略文件 |

---

## xqtrader backtest

运行策略回测，自动生成报告。

### 用法

```bash
xqtrader backtest [OPTIONS]
```

### 参数

| 参数 | 短写 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--strategy` | `-s` | 是 | — | 策略文件路径 (.py) |
| `--symbol` | | 是 | `BTC/USDT` | 交易对 |
| `--interval` | `-i` | 否 | `1m` | K线周期 (1m/5m/15m/1h/4h/1d) |
| `--start` | | 是 | — | 开始时间 |
| `--end` | | 是 | — | 结束时间 |
| `--capital` | | 否 | `10000.0` | 初始资金 (USDT) |
| `--contract` | | 否 | `futures` | 合约类型: `futures` / `events` |
| `--report` | `-r` | 否 | 自动生成 | 报告输出路径 (.json) |
| `--no-cache` | | 否 | `false` | 禁用数据缓存 |
| `--verbose` | `-v` | 否 | `false` | 显示详细交易日志 |

### 时间格式

支持以下格式（UTC 时区）：

- `YYYY-MM-DD` — 如 `2025-03-01`
- `YYYY-MM-DD HH:MM` — 如 `2025-03-01 08:00`
- `YYYY-MM-DD HH:MM:SS` — 如 `2025-03-01 08:00:00`

### 示例

```bash
# 基础回测
xqtrader backtest \
  -s examples/macd_strategy/macd_strategy.py \
  --symbol BTC/USDT \
  --start 2025-01-01 \
  --end 2025-03-01

# 指定资金、周期、合约类型
xqtrader backtest \
  -s my_strategy.py \
  --symbol ETH/USDT \
  -i 5m \
  --start "2025-02-01 08:00" \
  --end "2025-02-15 20:00" \
  --capital 50000 \
  --contract futures

# 详细模式 + 自定义报告路径
xqtrader backtest \
  -s my_strategy.py \
  --symbol BTC/USDT \
  --start 2025-01-01 \
  --end 2025-02-01 \
  -v \
  -r reports/btc_backtest.json

# 禁用缓存（强制重新获取数据）
xqtrader backtest \
  -s my_strategy.py \
  --symbol BTC/USDT \
  --start 2025-03-01 \
  --end 2025-03-02 \
  --no-cache
```

### 输出

回测完成后输出：

1. **回测报告摘要** — 收益、交易统计、风险指标三栏面板
2. **JSON 报告文件** — 默认保存为 `report_{策略名}_{交易对}_{合约类型}.json`

详细模式 (`-v`) 下还会实时输出每笔交易：

```
  #1  03-01 09:15  LONG long  @ 84521.0  PnL: +45.20
  #2  03-01 10:30  SHORT short  @ 84890.0  PnL: -12.10
```

---

## xqtrader strategy

策略管理命令组。

### xqtrader strategy list

列出指定目录下的所有策略文件。

```bash
xqtrader strategy list [OPTIONS]
```

| 参数 | 短写 | 默认值 | 说明 |
|------|------|--------|------|
| `--dir` | `-d` | `.` (当前目录) | 策略目录路径 |

```bash
# 列出当前目录的策略
xqtrader strategy list

# 指定目录
xqtrader strategy list -d examples/macd_strategy/
```

输出示例：

```
         可用策略
┌────────────────┬───────┬──────────────────┬──────────────────┐
│ 名称           │ 版本  │ 描述             │ 文件             │
├────────────────┼───────┼──────────────────┼──────────────────┤
│ macd_crossover │ 1.0.0 │ MACD 金叉死叉策略 │ macd_strategy.py │
└────────────────┴───────┴──────────────────┴──────────────────┘
```

### xqtrader strategy validate

校验策略文件是否可正确加载。

```bash
xqtrader strategy validate <FILE_PATH>
```

```bash
xqtrader strategy validate examples/macd_strategy/macd_strategy.py
```

输出示例：

```
校验通过
  名称: macd_crossover
  版本: 1.0.0
  描述: MACD 金叉死叉策略
  execute: 已实现
  指标需求: macd_1h
```

校验内容：
- 文件是否包含 `BaseStrategy` 子类
- `execute()` 方法是否已实现
- 指标需求声明

### xqtrader strategy new

生成策略模板文件。

```bash
xqtrader strategy new <NAME> [OPTIONS]
```

| 参数 | 短写 | 默认值 | 说明 |
|------|------|--------|------|
| `NAME` | | — | 策略名称（必填，如 `rsi_reversal`） |
| `--output` | `-o` | `{name}.py` | 输出文件路径 |

```bash
# 生成到当前目录
xqtrader strategy new rsi_reversal

# 指定输出路径
xqtrader strategy new bollinger_breakout -o strategies/bollinger_breakout.py
```

生成的模板包含 `BaseStrategy` 子类骨架，可直接编辑实现策略逻辑。

---

## 常用工作流

### 1. 从零开始回测一个策略

```bash
# 生成策略模板
xqtrader strategy new my_strategy

# 编辑策略逻辑
vim my_strategy.py

# 校验策略
xqtrader strategy validate my_strategy.py

# 运行回测
xqtrader backtest \
  -s my_strategy.py \
  --symbol BTC/USDT \
  --start 2025-01-01 \
  --end 2025-03-01 \
  -v
```

### 2. 批量回测多个交易对

```bash
for symbol in BTC/USDT ETH/USDT SOL/USDT; do
  xqtrader backtest \
    -s my_strategy.py \
    --symbol "$symbol" \
    --start 2025-01-01 \
    --end 2025-03-01 \
    -r "reports/${symbol//\//_}.json"
done
```

### 3. 不同时间周期对比

```bash
for interval in 1m 5m 15m 1h; do
  xqtrader backtest \
    -s my_strategy.py \
    --symbol BTC/USDT \
    -i "$interval" \
    --start 2025-01-01 \
    --end 2025-02-01 \
    -r "reports/btc_${interval}.json"
done
```
