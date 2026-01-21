from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


@dataclass
class StrategyDataRequirements:
    use_time_range: bool = True
    min_bars: int = 0
    prefer_closed_bar: bool = False
    extra_seconds: int = 0
    warmup_periods: int = 50
    max_timeframe_required: Optional[str] = None


@dataclass
class StrategySignal:
    """策略信号

    事件合约建议使用 UP/DOWN/HOLD，永续合约使用 LONG/SHORT/CLOSE_*。
    事件合约交易器会将 LONG/SHORT/BUY/SELL 兼容映射为 UP/DOWN。
    """
    action: str
    symbol: str
    quantity: float = 0.0
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    confidence: float = 1.0
    reason: str = ""


@dataclass
class StrategyContext:
    symbol: str
    interval: str
    current_time: datetime
    market_data: Dict[str, List[float]]
    indicators: Dict[str, Any] = field(default_factory=dict)
    incremental_indicators: Dict[str, Any] = field(default_factory=dict)
    account_balance: float = 0.0
    current_positions: Dict[str, float] = field(default_factory=dict)


@dataclass
class StrategyResult:
    signals: List[StrategySignal]
    indicators: Dict[str, Any]
    metadata: Dict[str, Any]
    execution_time: float
    success: bool
    error_message: Optional[str] = None


class BaseStrategy(ABC):
    """策略基类 - 所有用户策略必须继承此类"""

    def __init__(
        self,
        name: str,
        version: str = "1.0.0",
        description: str = "",
        tags: Optional[List[str]] = None,
    ) -> None:
        self.name = name
        self.version = version
        self.description = description
        self.tags = tags or []

    @abstractmethod
    def execute(self, context: StrategyContext) -> StrategyResult:
        """策略执行入口 - 必须实现"""

    def get_config(self) -> Dict[str, Any]:
        return {}

    def get_data_requirements(
        self, interval: str, config: Optional[Dict[str, Any]] = None
    ) -> StrategyDataRequirements:
        return StrategyDataRequirements()

    def get_indicator_requirements(self) -> Dict[str, Dict[str, Any]]:
        return {}

    def create_signal(
        self,
        action: str,
        symbol: str,
        quantity: float = 0.0,
        **kwargs: Any,
    ) -> StrategySignal:
        return StrategySignal(action=action, symbol=symbol, quantity=quantity, **kwargs)


@dataclass
class LoadedStrategyEntry:
    factory: Callable[[], BaseStrategy]
    module_name: str
    file_path: str
    metadata: Dict[str, Any]


class StrategyLoader:
    """策略加载器 - 动态加载 Python 策略文件"""

    def __init__(self, strategies_dir: str) -> None:
        self.strategies_dir = Path(strategies_dir)
        self.loaded_strategies: Dict[str, LoadedStrategyEntry] = {}

    def load_all_strategies(self) -> Dict[str, LoadedStrategyEntry]:
        for file_path in self.strategies_dir.glob("*.py"):
            self.load_strategy_from_file(str(file_path))
        return self.loaded_strategies

    def load_strategy_from_file(self, file_path: str) -> Optional[BaseStrategy]:
        import importlib.util
        import sys

        path = Path(file_path)
        if not path.exists():
            return None

        module_name = f"strategy_{path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            return None

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        strategy_cls = None
        strategy_instance = getattr(module, "strategy_instance", None)
        if strategy_instance and isinstance(strategy_instance, BaseStrategy):
            strategy_cls = strategy_instance.__class__
            def factory() -> BaseStrategy:
                try:
                    return strategy_cls(  # type: ignore[misc]
                        **{k: v for k, v in getattr(strategy_instance, "__dict__", {}).items() if k in {"name", "version", "description", "tags"}}
                    )
                except TypeError:
                    return strategy_cls(name=getattr(strategy_instance, "name", path.stem))  # type: ignore[misc]
        else:
            for attr in module.__dict__.values():
                if isinstance(attr, type) and issubclass(attr, BaseStrategy) and attr is not BaseStrategy:
                    strategy_cls = attr
                    break
            if strategy_cls is None:
                return None
            def factory() -> BaseStrategy:
                try:
                    return strategy_cls()  # type: ignore[misc]
                except TypeError:
                    return strategy_cls(name=path.stem)  # type: ignore[misc]

        if strategy_cls is None:
            return None

        instance = factory()
        metadata = {
            "name": getattr(instance, "name", path.stem),
            "version": getattr(instance, "version", "1.0.0"),
            "description": getattr(instance, "description", ""),
        }

        self.loaded_strategies[path.stem] = LoadedStrategyEntry(
            factory=factory, module_name=module_name, file_path=str(path), metadata=metadata
        )
        return instance

    def execute_strategy(self, strategy_id: str, context: StrategyContext) -> Optional[StrategyResult]:
        entry = self.loaded_strategies.get(strategy_id)
        if entry is None:
            return None
        strategy = entry.factory()
        return strategy.execute(context)

    def reload_strategy_from_file(self, file_path: str) -> bool:
        path = Path(file_path)
        if path.stem in self.loaded_strategies:
            del self.loaded_strategies[path.stem]
        return self.load_strategy_from_file(file_path) is not None
