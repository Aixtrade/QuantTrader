# XQTrader

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[中文文档](README.zh-CN.md)

A quantitative trading engine toolkit — create strategies, run backtests, and analyze results using natural language.

---

## Installation

Global install with [uv](https://github.com/astral-sh/uv) (recommended):

```bash
uv tool install "xqtrader[cli]"
```

Or add as a project dependency:

```bash
uv add "xqtrader[cli]"
```

Or with pip:

```bash
pip install "xqtrader[cli]"
```

> **Note**: zsh users must quote `"xqtrader[cli]"` to avoid glob interpretation.

### Upgrade

```bash
# uv global install
uv tool upgrade xqtrader

# uv project dependency
uv add --upgrade "xqtrader[cli]"

# pip
pip install --upgrade "xqtrader[cli]"
```

---

## Configure Your AI Tool

XQTrader provides skill files (in the `skills/` directory) that teach AI coding tools how to create strategies and run backtests.

Copy the contents of the `skills/` directory to the appropriate location for your tool:

| Tool | Target path |
|------|------------|
| [Claude Code](https://claude.ai/code) | Project: `.claude/skills/`, or personal: `~/.claude/skills/` |
| [OpenCode](https://opencode.ai) | `.opencode/skills/`, `.claude/skills/`, or `.agents/skills/` |
| [OpenClaw](https://docs.openclaw.ai) | Configure in `~/.openclaw/openclaw.json` |

For example, with Claude Code:

```bash
cp -r skills/* .claude/skills/
```

Once configured, you can use natural language or slash commands (`/create-strategy`, `/backtest`) for all operations.

---

## Usage

### Create a Strategy

Describe your strategy idea and Claude will generate a complete strategy file:

```
Create an RSI overbought/oversold reversal strategy
```

```
Build a MACD crossover strategy for 1h timeframe with trend filtering
```

```
I want a Bollinger Band breakout strategy for ranging markets
```

```
Create an event contract strategy based on RSI and volume to predict short-term direction
```

Or use the slash command for quick generation:

```
/create-strategy rsi_reversal
```

The generated strategy file includes indicator declarations and signal logic, ready for backtesting.

### Run a Backtest

Describe your backtest in natural language:

```
Backtest rsi_reversal.py on BTC/USDT for the last 3 months
```

```
Test this strategy on ETH/USDT from 2025-01-01 to 2025-03-01, 1h interval, 50k capital
```

```
Compare this strategy's performance on BTC and ETH
```

```
Backtest this strategy with event contracts on BTC/USDT for the last month
```

Or use the slash command:

```
/backtest rsi_reversal.py --symbol BTC/USDT --start 2025-01-01 --end 2025-03-01
```

Claude will validate the strategy, execute the backtest, and explain the results including returns, win rate, max drawdown, and Sharpe ratio.

### Iterate and Optimize

After backtesting, continue refining with natural language:

```
Win rate is too low, try changing the RSI oversold threshold from 30 to 25
```

```
Add a stop-loss at 2% drawdown
```

```
Switch to 4h timeframe and re-run the backtest
```

---

## Typical Workflow

```
1. Describe your strategy idea    →  Claude generates the strategy file
2. Review the generated code      →  Confirm or request changes
3. Say "run a backtest"           →  Claude executes and explains results
4. Suggest adjustments            →  Iterate and optimize
```

---

## Signal Types

| Contract Type | Signals |
|--------------|---------|
| Perpetual/Futures | `LONG`, `SHORT`, `CLOSE_LONG`, `CLOSE_SHORT`, `CLOSE` |
| Event Contracts | `UP`, `DOWN`, `HOLD` |

---

## Features

- **Natural Language Workflow**: Create and test strategies conversationally via Claude Code
- **60+ Technical Indicators**: RSI, MACD, Bollinger Bands, ATR, KDJ, and more
- **Multi-Exchange Support**: 100+ exchanges via CCXT
- **Futures Trading**: Perpetual futures with hedge mode position management
- **Risk Management**: Multi-level risk control (daily loss 3.5%/5%, max drawdown 10%/15%)

---

## Documentation

- [CLI Guide](docs/cli_guide.md) — Command-line reference
- [Development Guide](docs/development_guide.md) — Architecture and developer docs

---

## License

MIT License - see [LICENSE](LICENSE) for details.
