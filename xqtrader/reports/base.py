from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class EquityPoint:
    timestamp: datetime
    equity: float
    drawdown: float
    drawdown_pct: float


@dataclass
class TradeRecord:
    trade_id: str
    symbol: str
    action: str
    entry_time: datetime
    entry_price: float
    exit_time: datetime | None = None
    exit_price: float | None = None
    quantity: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    fees: float = 0.0
    holding_period: timedelta | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "action": self.action,
            "entry_time": self.entry_time.isoformat(),
            "entry_price": self.entry_price,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "exit_price": self.exit_price,
            "quantity": self.quantity,
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct,
            "fees": self.fees,
            "holding_period": self.holding_period.total_seconds() if self.holding_period else None,
        }


@dataclass
class BacktestReport:
    # ===== 基础信息 =====
    strategy_name: str
    symbol: str
    interval: str
    start_time: datetime
    end_time: datetime
    duration_days: int
    initial_capital: float
    final_capital: float

    # ===== 收益指标 =====
    total_return: float
    annual_return: float
    total_pnl: float

    # ===== 交易统计 =====
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    avg_holding_period: timedelta

    # ===== 风险指标 =====
    max_drawdown: float
    max_drawdown_pct: float
    max_drawdown_duration: timedelta
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float

    # ===== 详细数据 =====
    equity_curve: List[EquityPoint] = field(default_factory=list)
    trade_records: List[TradeRecord] = field(default_factory=list)
    monthly_returns: Dict[str, float] = field(default_factory=dict)
    daily_returns: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": {
                "strategy_name": self.strategy_name,
                "symbol": self.symbol,
                "interval": self.interval,
                "period": f"{self.start_time.isoformat()} - {self.end_time.isoformat()}",
                "duration_days": self.duration_days,
                "initial_capital": self.initial_capital,
                "final_capital": round(self.final_capital, 2),
            },
            "returns": {
                "total_return": round(self.total_return, 6),
                "annual_return": round(self.annual_return, 6),
                "total_pnl": round(self.total_pnl, 2),
            },
            "trades": {
                "total": self.total_trades,
                "winning": self.winning_trades,
                "losing": self.losing_trades,
                "win_rate": round(self.win_rate, 4),
                "avg_win": round(self.avg_win, 2),
                "avg_loss": round(self.avg_loss, 2),
                "profit_factor": round(self.profit_factor, 4),
                "avg_holding_period_seconds": self.avg_holding_period.total_seconds(),
            },
            "risk": {
                "max_drawdown": round(self.max_drawdown, 2),
                "max_drawdown_pct": round(self.max_drawdown_pct, 6),
                "max_drawdown_duration_seconds": self.max_drawdown_duration.total_seconds(),
                "sharpe_ratio": round(self.sharpe_ratio, 4),
                "sortino_ratio": round(self.sortino_ratio, 4),
                "calmar_ratio": round(self.calmar_ratio, 4),
            },
            "equity_curve": [
                {
                    "timestamp": ep.timestamp.isoformat(),
                    "equity": round(ep.equity, 2),
                    "drawdown": round(ep.drawdown, 2),
                    "drawdown_pct": round(ep.drawdown_pct, 6),
                }
                for ep in self.equity_curve
            ],
            "trade_records": [tr.to_dict() for tr in self.trade_records],
            "monthly_returns": {k: round(v, 6) for k, v in self.monthly_returns.items()},
            "daily_returns": [round(r, 6) for r in self.daily_returns],
        }


class ReportGenerator:
    TRADING_DAYS_PER_YEAR = 365
    RISK_FREE_RATE = 0.0

    @staticmethod
    def generate(
        trade_records: List[TradeRecord],
        equity_curve: List[EquityPoint],
        strategy_name: str,
        symbol: str,
        interval: str,
        initial_capital: float,
        final_capital: float,
    ) -> BacktestReport:
        if not equity_curve:
            now = datetime.now()
            return BacktestReport(
                strategy_name=strategy_name,
                symbol=symbol,
                interval=interval,
                start_time=now,
                end_time=now,
                duration_days=0,
                initial_capital=initial_capital,
                final_capital=final_capital,
                total_return=0.0,
                annual_return=0.0,
                total_pnl=0.0,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                avg_win=0.0,
                avg_loss=0.0,
                profit_factor=0.0,
                avg_holding_period=timedelta(),
                max_drawdown=0.0,
                max_drawdown_pct=0.0,
                max_drawdown_duration=timedelta(),
                sharpe_ratio=0.0,
                sortino_ratio=0.0,
                calmar_ratio=0.0,
                equity_curve=[],
                trade_records=[],
                monthly_returns={},
                daily_returns=[],
            )

        start_time = equity_curve[0].timestamp
        end_time = equity_curve[-1].timestamp
        duration = end_time - start_time
        duration_days = max(duration.days, 1)

        # ===== 收益指标 =====
        total_pnl = final_capital - initial_capital
        total_return = total_pnl / initial_capital if initial_capital > 0 else 0.0
        annual_return = ReportGenerator._annualize_return(total_return, duration_days)

        # ===== 交易统计 =====
        closed_trades = [t for t in trade_records if t.exit_time is not None]
        total_trades = len(closed_trades)
        wins = [t for t in closed_trades if t.pnl > 0]
        losses = [t for t in closed_trades if t.pnl <= 0]
        winning_trades = len(wins)
        losing_trades = len(losses)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0.0

        total_win_pnl = sum(t.pnl for t in wins)
        total_loss_pnl = abs(sum(t.pnl for t in losses))
        avg_win = total_win_pnl / winning_trades if winning_trades > 0 else 0.0
        avg_loss = total_loss_pnl / losing_trades if losing_trades > 0 else 0.0
        profit_factor = total_win_pnl / total_loss_pnl if total_loss_pnl > 0 else float("inf")

        holding_periods = [t.holding_period for t in closed_trades if t.holding_period is not None]
        avg_holding_period = (
            timedelta(seconds=sum(hp.total_seconds() for hp in holding_periods) / len(holding_periods))
            if holding_periods
            else timedelta()
        )

        # ===== 风险指标 - 回撤 =====
        max_dd = 0.0
        max_dd_pct = 0.0
        max_dd_duration = timedelta()
        peak_time: Optional[datetime] = None

        for ep in equity_curve:
            if ep.drawdown > max_dd:
                max_dd = ep.drawdown
            if ep.drawdown_pct > max_dd_pct:
                max_dd_pct = ep.drawdown_pct

            if ep.drawdown == 0:
                peak_time = ep.timestamp
            elif peak_time is not None:
                dd_dur = ep.timestamp - peak_time
                if dd_dur > max_dd_duration:
                    max_dd_duration = dd_dur

        # ===== 日收益率 =====
        daily_returns = ReportGenerator._compute_daily_returns(equity_curve)

        # ===== 月度收益 =====
        monthly_returns = ReportGenerator._compute_monthly_returns(equity_curve)

        # ===== 风险调整收益比率 =====
        sharpe_ratio = ReportGenerator._compute_sharpe(daily_returns)
        sortino_ratio = ReportGenerator._compute_sortino(daily_returns)
        calmar_ratio = annual_return / max_dd_pct if max_dd_pct > 0 else float("inf")

        return BacktestReport(
            strategy_name=strategy_name,
            symbol=symbol,
            interval=interval,
            start_time=start_time,
            end_time=end_time,
            duration_days=duration_days,
            initial_capital=initial_capital,
            final_capital=final_capital,
            total_return=total_return,
            annual_return=annual_return,
            total_pnl=total_pnl,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            avg_holding_period=avg_holding_period,
            max_drawdown=max_dd,
            max_drawdown_pct=max_dd_pct,
            max_drawdown_duration=max_dd_duration,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            equity_curve=equity_curve,
            trade_records=trade_records,
            monthly_returns=monthly_returns,
            daily_returns=daily_returns,
        )

    @staticmethod
    def _json_default(obj: Any) -> Any:
        if isinstance(obj, float):
            if math.isinf(obj):
                return "Infinity" if obj > 0 else "-Infinity"
            if math.isnan(obj):
                return "NaN"
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    @staticmethod
    def export(
        report: BacktestReport,
        format: str = "json",
        path: Optional[str] = None,
    ) -> str:
        if format == "json":
            def _sanitize(obj: Any) -> Any:
                if isinstance(obj, dict):
                    return {k: _sanitize(v) for k, v in obj.items()}
                if isinstance(obj, list):
                    return [_sanitize(v) for v in obj]
                if isinstance(obj, float) and (math.isinf(obj) or math.isnan(obj)):
                    return None
                return obj

            content = json.dumps(_sanitize(report.to_dict()), indent=2, ensure_ascii=False)
        else:
            raise ValueError(f"Unsupported format: {format}. Supported: json")

        if path is not None:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(content, encoding="utf-8")

        return content

    # ===== 内部计算方法 =====

    @staticmethod
    def _annualize_return(total_return: float, duration_days: int) -> float:
        if duration_days <= 0:
            return 0.0
        years = duration_days / ReportGenerator.TRADING_DAYS_PER_YEAR
        if years <= 0:
            return 0.0
        return (1 + total_return) ** (1 / years) - 1

    @staticmethod
    def _compute_daily_returns(equity_curve: List[EquityPoint]) -> List[float]:
        if len(equity_curve) < 2:
            return []

        daily_equities: Dict[str, float] = {}
        for ep in equity_curve:
            day_key = ep.timestamp.strftime("%Y-%m-%d")
            daily_equities[day_key] = ep.equity

        days = sorted(daily_equities.keys())
        if len(days) < 2:
            return []

        returns = []
        for i in range(1, len(days)):
            prev_eq = daily_equities[days[i - 1]]
            curr_eq = daily_equities[days[i]]
            r = (curr_eq - prev_eq) / prev_eq if prev_eq > 0 else 0.0
            returns.append(r)
        return returns

    @staticmethod
    def _compute_monthly_returns(equity_curve: List[EquityPoint]) -> Dict[str, float]:
        if len(equity_curve) < 2:
            return {}

        monthly_equities: Dict[str, float] = {}
        first_of_month: Dict[str, float] = {}

        for ep in equity_curve:
            month_key = ep.timestamp.strftime("%Y-%m")
            monthly_equities[month_key] = ep.equity
            if month_key not in first_of_month:
                first_of_month[month_key] = ep.equity

        months = sorted(monthly_equities.keys())
        result: Dict[str, float] = {}
        for i, month in enumerate(months):
            start_eq = first_of_month[month]
            if i > 0:
                start_eq = monthly_equities[months[i - 1]]
            end_eq = monthly_equities[month]
            result[month] = (end_eq - start_eq) / start_eq if start_eq > 0 else 0.0
        return result

    @staticmethod
    def _compute_sharpe(daily_returns: List[float], risk_free_rate: float = 0.0) -> float:
        if len(daily_returns) < 2:
            return 0.0
        daily_rf = risk_free_rate / ReportGenerator.TRADING_DAYS_PER_YEAR
        excess = [r - daily_rf for r in daily_returns]
        mean = sum(excess) / len(excess)
        variance = sum((r - mean) ** 2 for r in excess) / (len(excess) - 1)
        std = math.sqrt(variance) if variance > 0 else 0.0
        if std == 0:
            return 0.0
        return (mean / std) * math.sqrt(ReportGenerator.TRADING_DAYS_PER_YEAR)

    @staticmethod
    def _compute_sortino(daily_returns: List[float], risk_free_rate: float = 0.0) -> float:
        if len(daily_returns) < 2:
            return 0.0
        daily_rf = risk_free_rate / ReportGenerator.TRADING_DAYS_PER_YEAR
        excess = [r - daily_rf for r in daily_returns]
        mean = sum(excess) / len(excess)
        downside = [r for r in excess if r < 0]
        if not downside:
            return float("inf") if mean > 0 else 0.0
        downside_variance = sum(r**2 for r in downside) / (len(excess) - 1)
        downside_std = math.sqrt(downside_variance) if downside_variance > 0 else 0.0
        if downside_std == 0:
            return 0.0
        return (mean / downside_std) * math.sqrt(ReportGenerator.TRADING_DAYS_PER_YEAR)


class ReportCollector:
    """从引擎事件流中收集数据，自动构建报告。

    用法:
        collector = ReportCollector(strategy_name, symbol, interval, initial_capital)
        async for event in engine.run(strategy, config):
            collector.collect(event)
            # ... 自己的业务逻辑 ...
        report = collector.build()
        ReportGenerator.export(report, path="report.json")
    """

    def __init__(
        self,
        strategy_name: str,
        symbol: str,
        interval: str,
        initial_capital: float,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> None:
        self.strategy_name = strategy_name
        self.symbol = symbol
        self.interval = interval
        self.initial_capital = initial_capital
        self.final_capital = initial_capital
        self._start_ms = start_time
        self._end_ms = end_time

        self._equity_curve: List[EquityPoint] = []
        self._peak_equity: float = initial_capital
        self._open_trades: Dict[str, Dict[str, Any]] = {}  # side -> open trade info
        self._trade_records: List[TradeRecord] = []
        self._trade_counter: int = 0

    def collect(self, event: Any) -> None:
        event_type = event.event_type
        data = event.data

        if event_type == "tick":
            self._collect_tick(data)
        elif event_type == "trade":
            self._collect_trade(data)
        elif event_type == "complete":
            self.final_capital = data.get("final_balance", self.final_capital)

    def build(self) -> BacktestReport:
        return ReportGenerator.generate(
            trade_records=self._trade_records,
            equity_curve=self._equity_curve,
            strategy_name=self.strategy_name,
            symbol=self.symbol,
            interval=self.interval,
            initial_capital=self.initial_capital,
            final_capital=self.final_capital,
        )

    def _in_window(self, ts: int) -> bool:
        if self._start_ms is not None and ts < self._start_ms:
            return False
        if self._end_ms is not None and ts > self._end_ms:
            return False
        return True

    def _collect_tick(self, data: Dict[str, Any]) -> None:
        balance = data.get("account_balance")
        bar = data.get("bar", {})
        ts = bar.get("timestamp", 0)
        if balance is None or ts == 0:
            return
        if not self._in_window(ts):
            return

        equity = float(balance)
        self._peak_equity = max(self._peak_equity, equity)
        drawdown = self._peak_equity - equity
        drawdown_pct = drawdown / self._peak_equity if self._peak_equity > 0 else 0.0

        self._equity_curve.append(
            EquityPoint(
                timestamp=datetime.utcfromtimestamp(ts / 1000) if ts > 1e9 else datetime.utcfromtimestamp(ts),
                equity=equity,
                drawdown=drawdown,
                drawdown_pct=drawdown_pct,
            )
        )

    def _collect_trade(self, data: Dict[str, Any]) -> None:
        bar = data.get("bar", {})
        ts = bar.get("timestamp", 0)
        if not self._in_window(ts):
            return
        trade_time = datetime.utcfromtimestamp(ts / 1000) if ts > 1e9 else datetime.utcfromtimestamp(ts)
        price = bar.get("close", 0.0)
        trade_result = data.get("trade_result", {})

        # 永续合约: records 是列表
        records = data.get("records")
        if records and isinstance(records, list):
            for rec in records:
                self._process_futures_record(rec, trade_time, price, trade_result)
            return

        # 事件合约: record 是单个字典
        record = data.get("record")
        if record and isinstance(record, dict):
            self._process_events_record(record, trade_time, price, trade_result)

    def _process_futures_record(
        self, rec: Dict[str, Any], trade_time: datetime, price: float, trade_result: Dict[str, Any]
    ) -> None:
        action = rec.get("action", "")
        side = rec.get("side", "")
        size = rec.get("size", 0.0)
        trade_price = rec.get("price", price)

        action_upper = action.upper()
        is_open = action_upper in ("LONG", "SHORT", "BUY", "SELL", "OPEN_LONG", "OPEN_SHORT")
        is_close = action_upper.startswith("CLOSE")

        if is_open:
            self._open_trades[side] = {
                "entry_time": trade_time,
                "entry_price": trade_price,
                "size": size,
                "action": action,
                "side": side,
            }
        elif is_close:
            close_side = side
            if not close_side:
                if "LONG" in action_upper:
                    close_side = "long"
                elif "SHORT" in action_upper:
                    close_side = "short"

            open_trade = self._open_trades.pop(close_side, None)
            if open_trade:
                self._trade_counter += 1
                pnl = rec.get("pnl", trade_result.get("pnl", 0.0))
                fees = rec.get("fees", trade_result.get("fees", 0.0))
                entry_price = open_trade["entry_price"]
                nominal = entry_price * open_trade["size"]

                self._trade_records.append(
                    TradeRecord(
                        trade_id=f"T{self._trade_counter:04d}",
                        symbol=self.symbol,
                        action=open_trade["action"],
                        entry_time=open_trade["entry_time"],
                        entry_price=entry_price,
                        exit_time=trade_time,
                        exit_price=trade_price,
                        quantity=open_trade["size"],
                        pnl=pnl,
                        pnl_pct=pnl / nominal if nominal > 0 else 0.0,
                        fees=fees,
                        holding_period=trade_time - open_trade["entry_time"],
                    )
                )

    def _process_events_record(
        self, rec: Dict[str, Any], trade_time: datetime, price: float, trade_result: Dict[str, Any]
    ) -> None:
        if rec.get("skipped"):
            return

        self._trade_counter += 1
        pnl = trade_result.get("pnl", 0.0)
        fees = trade_result.get("fees", 0.0)

        self._trade_records.append(
            TradeRecord(
                trade_id=f"T{self._trade_counter:04d}",
                symbol=self.symbol,
                action=rec.get("action", ""),
                entry_time=trade_time,
                entry_price=price,
                exit_time=trade_time,
                exit_price=price,
                quantity=1.0,
                pnl=pnl,
                pnl_pct=pnl / price if price > 0 else 0.0,
                fees=fees,
                holding_period=timedelta(),
            )
        )
