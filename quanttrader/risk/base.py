from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from quanttrader.accounts.base import BaseAccount


class RiskLevel(str, Enum):
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


class RiskAction(str, Enum):
    NONE = "none"
    WARN = "warn"
    STOP_TRADING = "stop"
    FORCE_CLOSE = "force_close"


@dataclass
class RiskRule:
    name: str
    level: RiskLevel
    threshold: float
    action: RiskAction
    description: str = ""


@dataclass
class RiskConfig:
    max_daily_loss_pct: float = 0.05
    max_drawdown_pct: float = 0.15
    warning_ratio: float = 0.7


DEFAULT_RISK_RULES: List[RiskRule] = [
    RiskRule(
        name="daily_loss_warning",
        level=RiskLevel.WARNING,
        threshold=0.035,
        action=RiskAction.WARN,
        description="日亏损达到警告阈值",
    ),
    RiskRule(
        name="daily_loss_critical",
        level=RiskLevel.CRITICAL,
        threshold=0.05,
        action=RiskAction.FORCE_CLOSE,
        description="日亏损达到上限",
    ),
    RiskRule(
        name="max_drawdown_warning",
        level=RiskLevel.WARNING,
        threshold=0.10,
        action=RiskAction.WARN,
        description="回撤达到警告阈值",
    ),
    RiskRule(
        name="max_drawdown_critical",
        level=RiskLevel.CRITICAL,
        threshold=0.15,
        action=RiskAction.FORCE_CLOSE,
        description="回撤达到上限",
    ),
]


@dataclass
class RiskCheckResult:
    level: RiskLevel
    triggered_rules: List[RiskRule]
    recommended_action: RiskAction
    details: Dict[str, Any]


class RiskManager:
    def __init__(self, config: RiskConfig):
        self.config = config
        self.rules: List[RiskRule] = DEFAULT_RISK_RULES.copy()
        self.daily_pnl: float = 0.0
        self.peak_equity: float = 0.0
        self.current_equity: float = 0.0

    def check_risk(
        self,
        account: BaseAccount,
        positions: Dict[str, Any],
        trade_history: List[Any],
    ) -> RiskCheckResult:
        triggered: List[RiskRule] = []

        drawdown_rule = self._check_drawdown(account.balance)
        if drawdown_rule:
            triggered.append(drawdown_rule)

        if not triggered:
            return RiskCheckResult(
                level=RiskLevel.NORMAL,
                triggered_rules=[],
                recommended_action=RiskAction.NONE,
                details={},
            )

        max_level = max(r.level.value for r in triggered)
        max_action = max(r.action.value for r in triggered)
        return RiskCheckResult(
            level=RiskLevel(max_level),
            triggered_rules=triggered,
            recommended_action=RiskAction(max_action),
            details={"current_drawdown": self._calculate_drawdown()},
        )

    def _check_drawdown(self, current_balance: float) -> Optional[RiskRule]:
        self.current_equity = current_balance
        if current_balance > self.peak_equity:
            self.peak_equity = current_balance

        drawdown = self._calculate_drawdown()
        for rule in self.rules:
            if "drawdown" in rule.name and drawdown >= rule.threshold:
                return rule
        return None

    def _calculate_drawdown(self) -> float:
        if self.peak_equity <= 0:
            return 0.0
        return (self.peak_equity - self.current_equity) / self.peak_equity

    def reset_daily(self) -> None:
        self.daily_pnl = 0.0
