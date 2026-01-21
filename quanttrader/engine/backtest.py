from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

from quanttrader.accounts.futures import FuturesSimulatedAccount
from quanttrader.data.adapters.base import MarketType
from quanttrader.data.base import DataCenterService, MarketDataRequest
from quanttrader.engine.base import BaseEngine, ExecutionConfig, ExecutionEvent, ExecutionMode
from quanttrader.indicators.incremental import IndicatorBar, IndicatorEngine
from quanttrader.strategies.base import BaseStrategy, StrategyContext
from quanttrader.traders.futures import FuturesBacktestConfig, FuturesTrader, HedgePositionManager
from quanttrader.traders.events import EventsBacktestConfig, EventsTrader


@dataclass
class BacktestConfig(ExecutionConfig):
    initial_capital: float = 10000.0
    contract_type: str = "futures"  # futures | events (events 使用 UP/DOWN/HOLD)


class BacktestEngine(BaseEngine):
    def __init__(self) -> None:
        super().__init__(ExecutionMode.BACKTEST)

    @staticmethod
    def _interval_seconds(interval: str) -> int:
        normalized = interval.lower()
        if normalized.endswith("m"):
            return int(normalized[:-1]) * 60
        if normalized.endswith("h"):
            return int(normalized[:-1]) * 3600
        if normalized.endswith("d"):
            return int(normalized[:-1]) * 86400
        if normalized.endswith("w"):
            return int(normalized[:-1]) * 7 * 86400
        raise ValueError(f"unsupported interval: {interval}")

    async def run(
        self,
        strategy: BaseStrategy,
        config: ExecutionConfig,
        progress_callback: Optional[Any] = None,
    ) -> AsyncGenerator[ExecutionEvent, None]:
        if not isinstance(config, BacktestConfig):
            raise TypeError("config must be BacktestConfig")
        market_type = MarketType.FUTURES if config.contract_type == "futures" else MarketType.SPOT
        data_requirements = strategy.get_data_requirements(config.interval)
        start_time = config.start_time
        end_time = config.end_time

        request_limit = 100

        if data_requirements.use_time_range and start_time and end_time:
            interval_seconds = self._interval_seconds(config.interval)
            warmup_bars = max(data_requirements.min_bars, data_requirements.warmup_periods)
            if strategy.get_indicator_requirements():
                warmup_bars += 200
            warmup_ms = warmup_bars * interval_seconds * 1000
            extra_ms = data_requirements.extra_seconds * 1000
            start_time = max(0, start_time - warmup_ms - extra_ms)
            total_ms = max(0, end_time - start_time)
            required_bars = int(total_ms / (interval_seconds * 1000)) + 1
            request_limit = max(request_limit, required_bars)

        # 加载数据（MVP：占位空数据）
        async with DataCenterService(market_type=market_type) as data_service:
            market = await data_service.get_market_data(
                MarketDataRequest(
                    symbol=config.symbol,
                    interval=config.interval,
                    limit=request_limit,
                    start_time=start_time,
                    end_time=end_time,
                )
            )

        indicator_requirements = strategy.get_indicator_requirements()
        indicator_engine: Optional[IndicatorEngine] = None
        if indicator_requirements:
            indicator_engine = IndicatorEngine()
            indicator_engine.register_requirements(indicator_requirements)

        # 初始化账户和交易器
        if config.contract_type == "events":
            account = FuturesSimulatedAccount(config.initial_capital)  # 事件合约也复用资金账户
            trader = EventsTrader()
            trade_config = EventsBacktestConfig(symbol=config.symbol, interval=config.interval, investment_amount=100.0)
            position_manager = None
        else:
            account = FuturesSimulatedAccount(config.initial_capital)
            trader = FuturesTrader()
            trade_config = FuturesBacktestConfig(symbol=config.symbol, interval=config.interval)
            position_manager = HedgePositionManager(config.symbol)

        ohlcv = market.get("ohlcv", {})
        closes = ohlcv.get("close", [])
        opens = ohlcv.get("open", [])
        highs = ohlcv.get("high", [])
        lows = ohlcv.get("low", [])
        volumes = ohlcv.get("volume", [])
        timestamps = ohlcv.get("timestamps", [])

        all_signals: List[Any] = []
        for idx, close in enumerate(closes):
            bar = IndicatorBar(
                timestamp=int(timestamps[idx]) if idx < len(timestamps) else 0,
                open=opens[idx] if idx < len(opens) else close,
                high=highs[idx] if idx < len(highs) else close,
                low=lows[idx] if idx < len(lows) else close,
                close=close,
                volume=volumes[idx] if idx < len(volumes) else 0.0,
                timeframe=config.interval,
            )

            incremental_indicators: Dict[str, Any] = {}
            if indicator_engine:
                indicator_engine.update(bar)
                incremental_indicators = indicator_engine.snapshot()

            yield ExecutionEvent(
                event_type="tick",
                data={
                    "bar": {
                        "timestamp": bar.timestamp,
                        "open": bar.open,
                        "high": bar.high,
                        "low": bar.low,
                        "close": bar.close,
                        "volume": bar.volume,
                        "timeframe": bar.timeframe,
                    },
                    "incremental_indicators": incremental_indicators,
                },
                timestamp=datetime.utcnow(),
            )

            market_slice = {
                "timestamps": timestamps[: idx + 1],
                "open": opens[: idx + 1],
                "high": highs[: idx + 1],
                "low": lows[: idx + 1],
                "close": closes[: idx + 1],
                "volume": volumes[: idx + 1],
            }

            context = StrategyContext(
                symbol=config.symbol,
                interval=config.interval,
                current_time=datetime.utcnow(),
                market_data=market_slice,
                indicators={},
                incremental_indicators=incremental_indicators,
                account_balance=account.balance,
                current_positions={},
            )

            result = strategy.execute(context)
            signals: List[Any] = result.signals if result and result.signals else []

            for signal in signals:
                all_signals.append(signal)
                if isinstance(trader, EventsTrader):
                    trade_result, record = await trader.execute_trade(signal, close, account, trade_config)  # type: ignore[arg-type]
                    yield ExecutionEvent(
                        event_type="trade",
                        data={
                            "trade_result": trade_result.__dict__,
                            "record": record,
                            "bar": {
                                "timestamp": bar.timestamp,
                                "close": bar.close,
                                "timeframe": bar.timeframe,
                            },
                        },
                        timestamp=datetime.utcnow(),
                    )
                else:
                    trade_result, records = await trader.execute_trade(
                        signal,
                        close,
                        account,
                        trade_config,  # type: ignore[arg-type]
                        position_manager,
                    )
                    yield ExecutionEvent(
                        event_type="trade",
                        data={
                            "trade_result": trade_result.__dict__,
                            "records": records,
                            "bar": {
                                "timestamp": bar.timestamp,
                                "close": bar.close,
                                "timeframe": bar.timeframe,
                            },
                        },
                        timestamp=datetime.utcnow(),
                    )

        # 完成事件
        yield ExecutionEvent(
            event_type="complete",
            data={"final_balance": account.balance, "signals": [s.__dict__ for s in all_signals]},
            timestamp=datetime.utcnow(),
        )
