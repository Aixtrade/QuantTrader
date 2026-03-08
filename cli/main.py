"""QuantTrader CLI - 量化交易引擎命令行工具"""

from __future__ import annotations

import click

from quanttrader import __version__

from cli.commands.backtest import backtest
from cli.commands.strategy import strategy


@click.group()
@click.version_option(version=__version__, prog_name="QuantTrader")
def cli() -> None:
    """QuantTrader - 量化交易引擎"""
    pass


cli.add_command(backtest)
cli.add_command(strategy)
