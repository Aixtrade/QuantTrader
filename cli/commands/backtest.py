"""qt backtest - 策略回测命令"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import click

from cli.console import console, print_report_summary, print_trade_event


def _parse_time_ms(value: str) -> int:
    """将日期字符串解析为毫秒时间戳"""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
            return int(dt.timestamp() * 1000)
        except ValueError:
            continue
    raise click.BadParameter(f"无法解析日期: {value}，支持格式: YYYY-MM-DD [HH:MM[:SS]]")


@click.command()
@click.option(
    "--strategy", "-s",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="策略文件路径 (.py)",
)
@click.option("--symbol", required=True, default="BTC/USDT", show_default=True, help="交易对")
@click.option("--interval", "-i", default="1m", show_default=True, help="K线周期")
@click.option("--start", required=True, help="开始时间 (YYYY-MM-DD [HH:MM])")
@click.option("--end", required=True, help="结束时间 (YYYY-MM-DD [HH:MM])")
@click.option("--capital", default=10000.0, show_default=True, help="初始资金")
@click.option(
    "--contract",
    type=click.Choice(["futures", "events"], case_sensitive=False),
    default="futures",
    show_default=True,
    help="合约类型",
)
@click.option("--report", "-r", type=click.Path(), default=None, help="报告输出路径 (.json)")
@click.option("--no-cache", is_flag=True, default=False, help="禁用数据缓存")
@click.option("--verbose", "-v", is_flag=True, default=False, help="显示详细交易日志")
def backtest(
    strategy: str,
    symbol: str,
    interval: str,
    start: str,
    end: str,
    capital: float,
    contract: str,
    report: Optional[str],
    no_cache: bool,
    verbose: bool,
) -> None:
    """运行策略回测"""
    try:
        asyncio.run(_run_backtest(
            strategy_path=strategy,
            symbol=symbol,
            interval=interval,
            start=start,
            end=end,
            capital=capital,
            contract=contract,
            report_path=report,
            enable_cache=not no_cache,
            verbose=verbose,
        ))
    except KeyboardInterrupt:
        console.print("\n[yellow]回测已中断[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]回测失败: {e}[/red]")
        sys.exit(1)


async def _run_backtest(
    strategy_path: str,
    symbol: str,
    interval: str,
    start: str,
    end: str,
    capital: float,
    contract: str,
    report_path: Optional[str],
    enable_cache: bool,
    verbose: bool,
) -> None:
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

    from xqtrader.engine.backtest import BacktestConfig, BacktestEngine
    from xqtrader.reports.base import ReportCollector, ReportGenerator
    from xqtrader.strategies.base import StrategyLoader

    # 加载策略
    loader = StrategyLoader(str(Path(strategy_path).parent))
    strategy_instance = loader.load_strategy_from_file(strategy_path)
    if strategy_instance is None:
        console.print(f"[red]无法加载策略文件: {strategy_path}[/red]")
        console.print("[dim]确保文件包含继承 BaseStrategy 的策略类[/dim]")
        sys.exit(1)

    console.print(f"[green]策略已加载:[/green] {strategy_instance.name} v{strategy_instance.version}")

    start_ms = _parse_time_ms(start)
    end_ms = _parse_time_ms(end)

    config = BacktestConfig(
        symbol=symbol,
        interval=interval,
        initial_capital=capital,
        contract_type=contract,
        start_time=start_ms,
        end_time=end_ms,
        enable_cache=enable_cache,
    )

    collector = ReportCollector(
        strategy_name=strategy_instance.name,
        symbol=symbol,
        interval=interval,
        initial_capital=capital,
        start_time=start_ms,
        end_time=end_ms,
    )

    engine = BacktestEngine()
    tick_count = 0
    trade_count = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TextColumn("{task.fields[info]}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("回测中...", total=None, info="")

        async for event in engine.run(strategy_instance, config):
            collector.collect(event)

            if event.event_type == "tick":
                tick_count += 1
                bar = event.data.get("bar", {})
                progress.update(
                    task,
                    description=f"回测中... ({tick_count} bars)",
                    info=f"价格: {bar.get('close', 'N/A')}",
                )

            elif event.event_type == "trade":
                records = event.data.get("records", [])
                record = event.data.get("record")
                if records or (record and not record.get("skipped")):
                    trade_count += 1
                    if verbose:
                        progress.stop()
                        print_trade_event(trade_count, event.data)
                        progress.start()

            elif event.event_type == "complete":
                progress.update(task, description="回测完成", info="")

    # 构建报告
    report = collector.build()

    # 打印摘要
    print_report_summary(report)

    # 导出报告
    if report_path is None:
        report_path = f"report_{strategy_instance.name}_{symbol.replace('/', '_')}_{contract}.json"

    ReportGenerator.export(report, format="json", path=report_path)
    console.print(f"\n[dim]报告已导出: {report_path}[/dim]")
