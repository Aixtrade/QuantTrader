"""CLI 格式化输出工具"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

console = Console()


def print_report_summary(report: Any) -> None:
    """打印回测报告摘要"""
    summary = report.to_dict()

    s = summary["summary"]
    r = summary["returns"]
    t = summary["trades"]
    risk = summary["risk"]

    # 标题面板
    title = Text()
    title.append(f"{s['strategy_name']}", style="bold cyan")
    title.append(f"  {s['symbol']}  {s['interval']}", style="dim")

    # 收益表
    returns_table = Table(show_header=False, box=None, padding=(0, 2))
    returns_table.add_column("指标", style="dim")
    returns_table.add_column("值", justify="right")

    total_return = r["total_return"]
    total_pnl = r["total_pnl"]
    return_style = "green" if total_return >= 0 else "red"

    returns_table.add_row("总收益率", f"[{return_style}]{total_return:.2%}[/{return_style}]")
    returns_table.add_row("总盈亏", f"[{return_style}]{total_pnl:+.2f}[/{return_style}]")
    returns_table.add_row("年化收益", f"{r['annual_return']:.2%}")
    returns_table.add_row("初始资金", f"{s['initial_capital']:,.2f}")
    returns_table.add_row("最终资金", f"{s['final_capital']:,.2f}")

    # 交易统计表
    trades_table = Table(show_header=False, box=None, padding=(0, 2))
    trades_table.add_column("指标", style="dim")
    trades_table.add_column("值", justify="right")

    win_rate = t["win_rate"]
    wr_style = "green" if win_rate >= 0.5 else "yellow"

    trades_table.add_row("总交易", str(t["total"]))
    trades_table.add_row("胜/负", f"[green]{t['winning']}[/green] / [red]{t['losing']}[/red]")
    trades_table.add_row("胜率", f"[{wr_style}]{win_rate:.1%}[/{wr_style}]")
    trades_table.add_row("平均盈利", f"[green]{t['avg_win']:+.2f}[/green]")
    trades_table.add_row("平均亏损", f"[red]-{t['avg_loss']:.2f}[/red]")
    trades_table.add_row("盈亏比", f"{t['profit_factor']:.2f}")

    # 风险指标表
    risk_table = Table(show_header=False, box=None, padding=(0, 2))
    risk_table.add_column("指标", style="dim")
    risk_table.add_column("值", justify="right")

    mdd = risk["max_drawdown_pct"]
    mdd_style = "red" if mdd > 0.1 else "yellow" if mdd > 0.05 else "green"

    risk_table.add_row("最大回撤", f"[{mdd_style}]{mdd:.2%}[/{mdd_style}]")
    risk_table.add_row("夏普比率", f"{risk['sharpe_ratio']:.2f}")
    risk_table.add_row("索提诺比率", f"{risk['sortino_ratio']:.2f}")
    risk_table.add_row("卡尔玛比率", f"{risk['calmar_ratio']:.2f}")

    # 组合输出
    console.print()
    console.print(Panel(title, title="回测报告", border_style="blue"))

    overview = Table(show_header=True, box=None, padding=(0, 2))
    overview.add_column("收益", justify="center")
    overview.add_column("交易", justify="center")
    overview.add_column("风险", justify="center")
    overview.add_row(returns_table, trades_table, risk_table)

    console.print(overview)
    console.print(f"\n[dim]区间: {s['period']}  |  持续: {s['duration_days']} 天[/dim]")


def print_trade_event(trade_num: int, data: Dict[str, Any]) -> None:
    """打印单笔交易事件"""
    bar = data.get("bar", {})
    trade_result = data.get("trade_result", {})
    records = data.get("records", [])
    record = data.get("record")

    ts = bar.get("timestamp", 0)
    price = bar.get("close", 0)
    pnl = trade_result.get("pnl", 0.0)

    if records:
        action = records[0].get("action", "N/A")
        side = records[0].get("side", "")
    elif record:
        action = record.get("action", "N/A")
        side = ""
    else:
        action = "N/A"
        side = ""

    time_str = datetime.utcfromtimestamp(ts / 1000).strftime("%m-%d %H:%M") if ts > 1e9 else "N/A"
    pnl_style = "green" if pnl >= 0 else "red"
    action_display = f"{action} {side}".strip()

    console.print(
        f"  [dim]#{trade_num}[/dim]  {time_str}  "
        f"[bold]{action_display}[/bold]  "
        f"@ {price}  "
        f"PnL: [{pnl_style}]{pnl:+.2f}[/{pnl_style}]"
    )
