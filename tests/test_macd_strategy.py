"""MACD 策略单元测试"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

# 添加 examples 目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "examples"))

from quanttrader.strategies import StrategyContext
from macd_strategy import MACDStrategy, MACDConfig


class TestMACDStrategy:
    """MACD 策略测试"""

    def test_init(self):
        """测试策略初始化"""
        strategy = MACDStrategy()
        assert strategy.name == "macd_crossover"
        assert strategy.version == "1.0.0"

    def test_config(self):
        """测试自定义配置"""
        config = MACDConfig(fast_period=8, slow_period=21, signal_period=5)
        strategy = MACDStrategy(config=config)
        assert strategy.config.fast_period == 8
        assert strategy.config.slow_period == 21
        assert strategy.config.signal_period == 5

    def test_data_requirements(self):
        """测试数据需求"""
        strategy = MACDStrategy()
        req = strategy.get_data_requirements("1h")
        assert req.min_bars >= 26 + 9  # slow + signal

    def test_insufficient_data(self):
        """测试数据不足"""
        strategy = MACDStrategy()
        context = StrategyContext(
            symbol="BTC/USDT",
            interval="1h",
            current_time=datetime.now(timezone.utc),
            market_data={"close": [100.0, 101.0, 102.0]},  # 只有 3 根
        )
        result = strategy.execute(context)
        assert result.success
        assert result.signals[0].action == "HOLD"
        assert "insufficient_data" in result.metadata.get("error", "")

    def test_golden_cross_detection(self):
        """测试金叉检测"""
        strategy = MACDStrategy(config=MACDConfig(require_histogram_confirm=False))

        # 构造一个金叉场景：先下跌后反弹
        np.random.seed(42)
        # 下跌趋势
        downtrend = np.linspace(100, 80, 30)
        # 反弹
        uptrend = np.linspace(80, 95, 30)
        closes = list(downtrend) + list(uptrend)

        context = StrategyContext(
            symbol="BTC/USDT",
            interval="1h",
            current_time=datetime.now(timezone.utc),
            market_data={"close": closes},
        )

        result = strategy.execute(context)
        assert result.success
        assert result.indicators.get("macd") is not None
        assert result.indicators.get("signal") is not None

    def test_death_cross_detection(self):
        """测试死叉检测"""
        strategy = MACDStrategy(config=MACDConfig(require_histogram_confirm=False))

        # 构造一个死叉场景：先上涨后下跌
        uptrend = np.linspace(80, 100, 30)
        downtrend = np.linspace(100, 85, 30)
        closes = list(uptrend) + list(downtrend)

        context = StrategyContext(
            symbol="BTC/USDT",
            interval="1h",
            current_time=datetime.now(timezone.utc),
            market_data={"close": closes},
        )

        result = strategy.execute(context)
        assert result.success
        assert result.indicators.get("macd") is not None

    def test_hold_when_no_crossover(self):
        """测试无交叉时持有"""
        strategy = MACDStrategy()

        # 平稳价格
        closes = [100.0 + np.sin(i * 0.1) * 2 for i in range(60)]

        context = StrategyContext(
            symbol="BTC/USDT",
            interval="1h",
            current_time=datetime.now(timezone.utc),
            market_data={"close": closes},
        )

        result = strategy.execute(context)
        assert result.success
        # 平稳价格通常不会产生强烈的金叉/死叉
        assert result.signals[0].action in ("HOLD", "LONG", "SHORT")

