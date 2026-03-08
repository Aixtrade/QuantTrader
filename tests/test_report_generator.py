from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from quanttrader.reports.base import (
    BacktestReport,
    EquityPoint,
    ReportGenerator,
    TradeRecord,
)


def _make_equity_curve(
    start: datetime,
    equities: list[float],
    interval_hours: int = 24,
) -> list[EquityPoint]:
    peak = equities[0]
    points = []
    for i, eq in enumerate(equities):
        ts = start + timedelta(hours=interval_hours * i)
        peak = max(peak, eq)
        dd = peak - eq
        dd_pct = dd / peak if peak > 0 else 0.0
        points.append(EquityPoint(timestamp=ts, equity=eq, drawdown=dd, drawdown_pct=dd_pct))
    return points


def _make_trade(
    trade_id: str,
    entry_time: datetime,
    exit_time: datetime,
    pnl: float,
    entry_price: float = 100.0,
    exit_price: float = 110.0,
    quantity: float = 1.0,
    fees: float = 1.0,
) -> TradeRecord:
    return TradeRecord(
        trade_id=trade_id,
        symbol="BTC/USDT",
        action="LONG",
        entry_time=entry_time,
        entry_price=entry_price,
        exit_time=exit_time,
        exit_price=exit_price,
        quantity=quantity,
        pnl=pnl,
        pnl_pct=pnl / (entry_price * quantity) if entry_price * quantity > 0 else 0.0,
        fees=fees,
        holding_period=exit_time - entry_time,
    )


class TestReportGeneratorGenerate:
    def test_empty_equity_curve(self):
        report = ReportGenerator.generate(
            trade_records=[],
            equity_curve=[],
            strategy_name="test",
            symbol="BTC/USDT",
            interval="1h",
            initial_capital=10000.0,
            final_capital=10000.0,
        )
        assert report.total_trades == 0
        assert report.total_return == 0.0
        assert report.sharpe_ratio == 0.0

    def test_basic_profitable_backtest(self):
        start = datetime(2024, 1, 1)
        equities = [10000, 10200, 10500, 10300, 10800, 11000]
        curve = _make_equity_curve(start, equities)

        trades = [
            _make_trade("t1", start, start + timedelta(days=1), pnl=200),
            _make_trade("t2", start + timedelta(days=1), start + timedelta(days=2), pnl=300),
            _make_trade("t3", start + timedelta(days=2), start + timedelta(days=3), pnl=-200),
            _make_trade("t4", start + timedelta(days=3), start + timedelta(days=4), pnl=500),
            _make_trade("t5", start + timedelta(days=4), start + timedelta(days=5), pnl=200),
        ]

        report = ReportGenerator.generate(
            trade_records=trades,
            equity_curve=curve,
            strategy_name="macd_strategy",
            symbol="BTC/USDT",
            interval="1h",
            initial_capital=10000.0,
            final_capital=11000.0,
        )

        assert report.strategy_name == "macd_strategy"
        assert report.symbol == "BTC/USDT"
        assert report.total_pnl == 1000.0
        assert report.total_return == pytest.approx(0.1)
        assert report.total_trades == 5
        assert report.winning_trades == 4
        assert report.losing_trades == 1
        assert report.win_rate == pytest.approx(0.8)
        assert report.max_drawdown_pct > 0
        assert report.annual_return > 0

    def test_profit_factor(self):
        start = datetime(2024, 1, 1)
        equities = [10000, 10500, 10200]
        curve = _make_equity_curve(start, equities)

        trades = [
            _make_trade("t1", start, start + timedelta(days=1), pnl=500),
            _make_trade("t2", start + timedelta(days=1), start + timedelta(days=2), pnl=-300),
        ]

        report = ReportGenerator.generate(
            trade_records=trades,
            equity_curve=curve,
            strategy_name="test",
            symbol="BTC/USDT",
            interval="1h",
            initial_capital=10000.0,
            final_capital=10200.0,
        )

        assert report.profit_factor == pytest.approx(500 / 300)
        assert report.avg_win == pytest.approx(500.0)
        assert report.avg_loss == pytest.approx(300.0)

    def test_all_winning_trades(self):
        start = datetime(2024, 1, 1)
        equities = [10000, 10500, 11000]
        curve = _make_equity_curve(start, equities)

        trades = [
            _make_trade("t1", start, start + timedelta(days=1), pnl=500),
            _make_trade("t2", start + timedelta(days=1), start + timedelta(days=2), pnl=500),
        ]

        report = ReportGenerator.generate(
            trade_records=trades,
            equity_curve=curve,
            strategy_name="test",
            symbol="BTC/USDT",
            interval="1h",
            initial_capital=10000.0,
            final_capital=11000.0,
        )

        assert report.win_rate == 1.0
        assert report.profit_factor == float("inf")
        assert report.avg_loss == 0.0
        assert report.max_drawdown == 0.0

    def test_max_drawdown_duration(self):
        start = datetime(2024, 1, 1)
        # Peak at day 0, drawdown from day 1-3, recovery at day 4
        equities = [10000, 9500, 9200, 9800, 10000]
        curve = _make_equity_curve(start, equities)

        report = ReportGenerator.generate(
            trade_records=[],
            equity_curve=curve,
            strategy_name="test",
            symbol="BTC/USDT",
            interval="1h",
            initial_capital=10000.0,
            final_capital=10000.0,
        )

        assert report.max_drawdown == pytest.approx(800.0)
        assert report.max_drawdown_pct == pytest.approx(0.08)
        # Drawdown from day 0 (peak) to day 3 (last point before recovery)
        assert report.max_drawdown_duration == timedelta(hours=72)

    def test_open_trades_excluded_from_stats(self):
        start = datetime(2024, 1, 1)
        equities = [10000, 10500]
        curve = _make_equity_curve(start, equities)

        open_trade = TradeRecord(
            trade_id="t1",
            symbol="BTC/USDT",
            action="LONG",
            entry_time=start,
            entry_price=100.0,
            quantity=1.0,
        )

        report = ReportGenerator.generate(
            trade_records=[open_trade],
            equity_curve=curve,
            strategy_name="test",
            symbol="BTC/USDT",
            interval="1h",
            initial_capital=10000.0,
            final_capital=10500.0,
        )

        assert report.total_trades == 0


class TestReportGeneratorExport:
    def test_export_json_string(self):
        start = datetime(2024, 1, 1)
        equities = [10000, 10500]
        curve = _make_equity_curve(start, equities)

        report = ReportGenerator.generate(
            trade_records=[],
            equity_curve=curve,
            strategy_name="test",
            symbol="BTC/USDT",
            interval="1h",
            initial_capital=10000.0,
            final_capital=10500.0,
        )

        result = ReportGenerator.export(report)
        data = json.loads(result)
        assert data["summary"]["strategy_name"] == "test"
        assert data["returns"]["total_pnl"] == 500.0

    def test_export_json_file(self, tmp_path):
        start = datetime(2024, 1, 1)
        equities = [10000, 10500]
        curve = _make_equity_curve(start, equities)

        report = ReportGenerator.generate(
            trade_records=[],
            equity_curve=curve,
            strategy_name="test",
            symbol="BTC/USDT",
            interval="1h",
            initial_capital=10000.0,
            final_capital=10500.0,
        )

        file_path = str(tmp_path / "reports" / "test_report.json")
        ReportGenerator.export(report, format="json", path=file_path)

        assert Path(file_path).exists()
        data = json.loads(Path(file_path).read_text())
        assert data["summary"]["strategy_name"] == "test"

    def test_export_unsupported_format(self):
        start = datetime(2024, 1, 1)
        curve = _make_equity_curve(start, [10000])

        report = ReportGenerator.generate(
            trade_records=[],
            equity_curve=curve,
            strategy_name="test",
            symbol="BTC/USDT",
            interval="1h",
            initial_capital=10000.0,
            final_capital=10000.0,
        )

        with pytest.raises(ValueError, match="Unsupported format"):
            ReportGenerator.export(report, format="html")


class TestDailyAndMonthlyReturns:
    def test_daily_returns_calculation(self):
        start = datetime(2024, 1, 1)
        equities = [10000, 10100, 10300, 10200]
        curve = _make_equity_curve(start, equities)

        report = ReportGenerator.generate(
            trade_records=[],
            equity_curve=curve,
            strategy_name="test",
            symbol="BTC/USDT",
            interval="1h",
            initial_capital=10000.0,
            final_capital=10200.0,
        )

        assert len(report.daily_returns) == 3
        assert report.daily_returns[0] == pytest.approx(0.01)
        assert report.daily_returns[1] == pytest.approx(200 / 10100)

    def test_monthly_returns_populated(self):
        start = datetime(2024, 1, 1)
        # Span 2 months
        equities = [10000]
        for i in range(1, 60):
            equities.append(10000 + i * 10)
        curve = _make_equity_curve(start, equities)

        report = ReportGenerator.generate(
            trade_records=[],
            equity_curve=curve,
            strategy_name="test",
            symbol="BTC/USDT",
            interval="1h",
            initial_capital=10000.0,
            final_capital=equities[-1],
        )

        assert len(report.monthly_returns) > 0


class TestSharpeAndSortino:
    def test_sharpe_positive_returns(self):
        start = datetime(2024, 1, 1)
        equities = [10000 + i * 50 for i in range(30)]
        curve = _make_equity_curve(start, equities)

        report = ReportGenerator.generate(
            trade_records=[],
            equity_curve=curve,
            strategy_name="test",
            symbol="BTC/USDT",
            interval="1h",
            initial_capital=10000.0,
            final_capital=equities[-1],
        )

        assert report.sharpe_ratio > 0

    def test_sortino_no_downside(self):
        start = datetime(2024, 1, 1)
        equities = [10000 + i * 50 for i in range(10)]
        curve = _make_equity_curve(start, equities)

        report = ReportGenerator.generate(
            trade_records=[],
            equity_curve=curve,
            strategy_name="test",
            symbol="BTC/USDT",
            interval="1h",
            initial_capital=10000.0,
            final_capital=equities[-1],
        )

        assert report.sortino_ratio == float("inf")
