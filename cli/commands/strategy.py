"""qt strategy - 策略管理命令"""

from __future__ import annotations

from pathlib import Path

import click

from cli.console import console


@click.group()
def strategy() -> None:
    """策略管理"""
    pass


@strategy.command("list")
@click.option(
    "--dir", "-d",
    type=click.Path(exists=True, file_okay=False),
    default=".",
    help="策略目录",
)
def list_strategies(dir: str) -> None:
    """列出目录下的策略文件"""
    from rich.table import Table

    from xqtrader.strategies.base import StrategyLoader

    loader = StrategyLoader(dir)
    skipped = []
    for file_path in Path(dir).glob("*.py"):
        try:
            loader.load_strategy_from_file(str(file_path))
        except Exception:
            skipped.append(file_path.name)
    entries = loader.loaded_strategies

    if skipped:
        console.print(f"[dim]跳过非策略文件: {', '.join(skipped)}[/dim]")

    if not entries:
        console.print(f"[yellow]在 {dir} 下未找到策略文件[/yellow]")
        return

    table = Table(title="可用策略")
    table.add_column("名称", style="cyan")
    table.add_column("版本", style="green")
    table.add_column("描述")
    table.add_column("文件", style="dim")

    for _key, entry in entries.items():
        meta = entry.metadata
        table.add_row(
            meta.get("name", "N/A"),
            meta.get("version", "N/A"),
            meta.get("description", ""),
            str(Path(entry.file_path).name),
        )

    console.print(table)


@strategy.command("validate")
@click.argument("file_path", type=click.Path(exists=True, dir_okay=False))
def validate_strategy(file_path: str) -> None:
    """校验策略文件是否可加载"""
    from xqtrader.strategies.base import StrategyLoader

    loader = StrategyLoader(str(Path(file_path).parent))
    instance = loader.load_strategy_from_file(file_path)

    if instance is None:
        console.print(f"[red]校验失败:[/red] 未找到有效的 BaseStrategy 子类")
        raise SystemExit(1)

    console.print(f"[green]校验通过[/green]")
    console.print(f"  名称: {instance.name}")
    console.print(f"  版本: {instance.version}")
    console.print(f"  描述: {instance.description or '(无)'}")

    # 检查 execute 方法
    from xqtrader.strategies.base import BaseStrategy
    if hasattr(instance, "execute") and callable(instance.execute):
        console.print(f"  execute: [green]已实现[/green]")
    else:
        console.print(f"  execute: [red]未实现[/red]")

    # 检查指标需求
    indicator_reqs = instance.get_indicator_requirements()
    if indicator_reqs:
        console.print(f"  指标需求: {', '.join(indicator_reqs.keys())}")
    else:
        console.print(f"  指标需求: (无)")


@strategy.command("new")
@click.argument("name")
@click.option("--output", "-o", type=click.Path(), default=None, help="输出路径")
def new_strategy(name: str, output: str | None) -> None:
    """生成策略模板文件"""
    template = '''"""策略: {name}"""

from __future__ import annotations

from xqtrader.strategies.base import BaseStrategy, StrategyContext, StrategyResult


class {class_name}(BaseStrategy):
    def __init__(self) -> None:
        super().__init__(
            name="{name}",
            version="1.0.0",
            description="",
        )

    def execute(self, context: StrategyContext) -> StrategyResult:
        closes = context.market_data.get("close", [])
        if not closes:
            return StrategyResult(
                signals=[], indicators={{}}, metadata={{}},
                execution_time=0.0, success=True,
            )

        current_price = closes[-1]

        # TODO: 实现你的策略逻辑
        signals = []

        return StrategyResult(
            signals=signals,
            indicators={{}},
            metadata={{"price": current_price}},
            execution_time=0.0,
            success=True,
        )
'''

    class_name = "".join(word.capitalize() for word in name.replace("-", "_").split("_")) + "Strategy"
    content = template.format(name=name, class_name=class_name)

    if output is None:
        output = f"{name.replace('-', '_')}.py"

    path = Path(output)
    if path.exists():
        console.print(f"[red]文件已存在: {output}[/red]")
        raise SystemExit(1)

    path.write_text(content, encoding="utf-8")
    console.print(f"[green]策略模板已生成: {output}[/green]")
