---
name: backtest
description: 运行 XQTrader 策略回测。当用户要求回测策略、测试策略表现、查看策略收益时使用此技能。
argument-hint: [策略文件路径] [--symbol BTC/USDT] [--start 2025-01-01] [--end 2025-03-01]
---

# 运行 XQTrader 策略回测

你正在帮助用户使用 XQTrader CLI 执行策略回测。通过 `xqt backtest` 命令运行。

前置条件：用户已安装 `pip install xqtrader[cli]`。

## 命令格式

```bash
xqt backtest \
  --strategy <策略文件.py> \
  --symbol <交易对> \
  --start <开始日期> \
  --end <结束日期> \
  [--interval <K线周期>] \
  [--capital <初始资金>] \
  [--contract <合约类型>] \
  [--report <报告路径.json>] \
  [--verbose]
```

## 参数说明

| 参数 | 短写 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--strategy` | `-s` | 是 | - | 策略文件路径（.py） |
| `--symbol` | | 是 | `BTC/USDT` | 交易对 |
| `--start` | | 是 | - | 开始时间（YYYY-MM-DD [HH:MM[:SS]]） |
| `--end` | | 是 | - | 结束时间（YYYY-MM-DD [HH:MM[:SS]]） |
| `--interval` | `-i` | 否 | `1m` | K线周期：1m/5m/15m/1h/4h/1d |
| `--capital` | | 否 | `10000.0` | 初始资金（USDT） |
| `--contract` | | 否 | `futures` | 合约类型：futures/events |
| `--report` | `-r` | 否 | 自动生成 | 报告输出路径（.json） |
| `--no-cache` | | 否 | false | 禁用数据缓存 |
| `--verbose` | `-v` | 否 | false | 显示详细交易日志 |

## 执行流程

### 第1步：确认策略文件存在

检查用户指定的策略文件是否存在。如果用户没有策略文件，提示使用 `create-strategy` skill 创建。

### 第2步：确定回测参数

从用户描述中提取参数，未指定的使用默认值：

- **交易对**：默认 `BTC/USDT`
- **时间范围**：必须由用户提供
- **K线周期**：根据时间范围建议合理周期
  - 1-7 天 → `1m` 或 `5m`
  - 1-4 周 → `15m` 或 `1h`
  - 1-6 月 → `1h` 或 `4h`
  - 6 月以上 → `4h` 或 `1d`
- **初始资金**：默认 10000 USDT
- **合约类型**：默认 `futures`（永续合约）

### 第3步：先校验策略

```bash
xqt strategy validate <策略文件.py>
```

校验通过后再执行回测。

### 第4步：执行回测

```bash
xqt backtest \
  -s my_strategy.py \
  --symbol BTC/USDT \
  --start 2025-01-01 \
  --end 2025-03-01 \
  --interval 1h \
  --capital 10000 \
  --contract futures \
  --verbose
```

### 第5步：解读结果

回测完成后，CLI 输出包含三部分：

**收益指标**：
- 总收益率、总盈亏
- 年化收益
- 初始/最终资金

**交易统计**：
- 总交易数、胜/负比
- 胜率、平均盈利/亏损
- 盈亏比（profit factor）

**风险指标**：
- 最大回撤
- 夏普比率（> 1 为佳，> 2 为优秀）
- 索提诺比率
- 卡尔玛比率

向用户解释这些指标的含义和策略表现。

## 示例

### 基础回测

```bash
xqt backtest -s rsi_strategy.py --symbol BTC/USDT --start 2025-01-01 --end 2025-03-01 --interval 1h
```

### 详细回测（显示每笔交易）

```bash
xqt backtest -s macd_strategy.py --symbol ETH/USDT --start 2025-02-01 --end 2025-03-01 -i 15m --capital 50000 -v
```

### 事件合约回测

```bash
xqt backtest -s my_strategy.py --symbol BTC/USDT --start 2025-01-01 --end 2025-02-01 --contract events
```

## 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| "无法加载策略文件" | 文件中没有 BaseStrategy 子类 | 用 `xqt strategy validate` 检查 |
| "无法解析日期" | 日期格式不对 | 使用 YYYY-MM-DD 格式 |
| 回测无交易 | 策略一直返回 HOLD | 检查信号逻辑和指标预热 |
| 收益为 0 | 可能预热期覆盖了整个回测区间 | 增大时间范围或减小指标周期 |

## 其他策略管理命令

```bash
# 列出目录下的策略
xqt strategy list --dir .

# 校验策略文件
xqt strategy validate my_strategy.py

# 生成策略模板
xqt strategy new my_strategy
```
