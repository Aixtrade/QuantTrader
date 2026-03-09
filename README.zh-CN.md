# XQTrader

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[English](README.md)

量化交易引擎工具包 — 通过自然语言创建策略、运行回测、分析结果。

<video src="https://github.com/Aixtrade/QuantTrader/raw/main/assets/create-strategy-demo.mp4" controls width="100%"></video>

---

## 安装

使用 [uv](https://github.com/astral-sh/uv) 全局安装（推荐）：

```bash
uv tool install "xqtrader[cli]"
```

或添加到项目依赖：

```bash
uv add "xqtrader[cli]"
```

或使用 pip：

```bash
pip install "xqtrader[cli]"
```

> **注意**：zsh 用户必须用引号包裹 `"xqtrader[cli]"`，否则 `[]` 会被解释为 glob 语法。

### 升级

```bash
# uv 全局安装
uv tool upgrade xqtrader

# uv 项目依赖
uv add --upgrade "xqtrader[cli]"

# pip
pip install --upgrade "xqtrader[cli]"
```

---

## 配置 AI 工具

XQTrader 提供了 skills 文件（位于 `skills/` 目录），用于让 AI 编码工具理解如何创建策略和运行回测。

根据你使用的 AI 编码工具，将 `skills/` 目录下的内容复制到对应位置：

| 工具 | 目标路径 |
|------|---------|
| [Claude Code](https://claude.ai/code) | 项目级：`.claude/skills/`，或个人级：`~/.claude/skills/` |
| [OpenCode](https://opencode.ai) | `.opencode/skills/`、`.claude/skills/` 或 `.agents/skills/` |
| [OpenClaw](https://docs.openclaw.ai) | `~/.openclaw/openclaw.json` 中配置 |

以 Claude Code 为例：

```bash
cp -r skills/* .claude/skills/
```

配置完成后，即可通过自然语言或斜杠命令（如 `/create-strategy`、`/backtest`）完成所有操作。

---

## 使用方式

### 创建策略

直接描述你的策略想法，Claude 会生成完整的策略文件：

```
帮我创建一个 RSI 超买超卖反转策略
```

```
创建一个 MACD 金叉死叉策略，5 分钟周期，带趋势过滤
```

```
我想做一个布林带突破策略，适合震荡行情
```

```
创建一个事件合约策略，基于 RSI 和成交量判断短期涨跌方向
```

也可以使用斜杠命令快速生成：

```
/create-strategy rsi_reversal
```

生成的策略文件包含完整的指标声明和信号逻辑，可直接用于回测。

### 运行回测

用自然语言描述回测需求：

```
用 rsi_reversal.py 回测 BTC/USDT，最近三个月
```

```
回测一下这个策略在 ETH/USDT 上的表现，从 2025-01-01 到 2025-03-01，1h 周期，5 万资金
```

```
对比一下这个策略在 BTC 和 ETH 上的表现
```

```
用事件合约模式回测这个策略，BTC/USDT，最近 1 小时，通过回测结果评估其效果
```

也可以使用斜杠命令：

```
/backtest rsi_reversal.py --symbol BTC/USDT --start 2025-01-01 --end 2025-03-01
```

Claude 会校验策略、执行回测，并解读结果，包括收益率、胜率、最大回撤和夏普比率等指标。

### 优化迭代

回测完成后，继续用自然语言调整：

```
胜率太低了，把 RSI 超卖阈值从 30 调到 25 试试
```

```
加一个止损逻辑，亏损 2% 自动平仓
```

```
换成 4h 周期重新回测看看
```

---

## 典型工作流

```
1. 描述策略想法          →  Claude 生成策略文件
2. 检查生成的策略代码     →  确认或提出修改
3. 说「回测一下」         →  Claude 执行回测并解读结果
4. 根据结果提出调整       →  迭代优化
```

---

## 信号类型

| 合约类型 | 信号 |
|---------|------|
| 永续/期货 | `LONG`, `SHORT`, `CLOSE_LONG`, `CLOSE_SHORT`, `CLOSE` |
| 事件合约 | `UP`, `DOWN`, `HOLD` |

---

## 功能特性

- **自然语言交互**：通过 Claude Code 用对话方式创建和测试策略
- **60+ 技术指标**：RSI、MACD、布林带、ATR、KDJ 等
- **多交易所支持**：通过 CCXT 支持 100+ 交易所
- **合约交易**：永续合约双向持仓模式
- **风控系统**：分级风控（日亏损 3.5%/5%，最大回撤 10%/15%）

---

## 文档

- [CLI 使用指南](docs/cli_guide.md) — 命令行参考
- [开发指南](docs/development_guide.md) — 架构与开发者文档

---

## 许可证

MIT License - 详见 [LICENSE](LICENSE)。
