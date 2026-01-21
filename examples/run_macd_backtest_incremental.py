"""MACD 增量回测示例"""

from __future__ import annotations

import asyncio

from datetime import datetime, timedelta, timezone

from quanttrader.engine.backtest import BacktestConfig, BacktestEngine
from macd_strategy import MACDConfig, MACDStrategy


async def main() -> None:
    macd_config = MACDConfig(
        timeframe="1h",
        require_histogram_confirm=False,
    )
    strategy = MACDStrategy(config=macd_config)

    engine = BacktestEngine()
    now = datetime.now(timezone.utc)
    last_closed = now.replace(minute=0, second=0, microsecond=0)
    if last_closed > now:
        last_closed -= timedelta(hours=1)
    end_time = int(last_closed.timestamp() * 1000)
    start_time = int((last_closed - timedelta(hours=6)).timestamp() * 1000)

    requested_start_time = start_time
    requested_end_time = end_time

    config = BacktestConfig(
        symbol="BTC/USDT",
        interval="1h",
        initial_capital=10000.0,
        start_time=start_time,
        end_time=end_time,
    )

    indicator_id = f"macd_{macd_config.timeframe}"
    bar_index = 0
    warmed_up = False

    local_tz = datetime.now().astimezone().tzinfo

    async for event in engine.run(strategy, config):
        if event.event_type == "tick":
            bar_index += 1
            bar = event.data.get("bar", {})
            indicators = event.data.get("incremental_indicators", {})
            macd_payload = indicators.get("macd", {}).get(indicator_id, {})
            timeframe_state = indicators.get("by_timeframe", {}).get(macd_config.timeframe, {})
            is_warmed_up = timeframe_state.get("is_warmed_up", indicators.get("is_warmed_up", False))
            warmed_up = is_warmed_up
            if not is_warmed_up:
                continue
            bar_ts = bar.get("timestamp")
            if (
                isinstance(bar_ts, int)
                and requested_start_time is not None
                and requested_end_time is not None
                and (bar_ts < requested_start_time or bar_ts > requested_end_time)
            ):
                continue

            bar_time = None
            if isinstance(bar_ts, int) and bar_ts > 0:
                bar_time = datetime.fromtimestamp(bar_ts / 1000).astimezone(local_tz)

            print(
                " | ".join(
                    [
                        f"#{bar_index}",
                        f"time={bar_time.isoformat() if bar_time else 'N/A'}",
                        f"close={bar.get('close')}",
                        f"macd={macd_payload.get('macd')}",
                        f"signal={macd_payload.get('signal_line')}",
                        f"hist={macd_payload.get('histogram')}",
                    ]
                )
            )
        if event.event_type == "trade":
            trade_bar = event.data.get("bar", {})
            trade_ts = trade_bar.get("timestamp")
            if (
                not warmed_up
                or not isinstance(trade_ts, int)
                or trade_ts < requested_start_time
                or trade_ts > requested_end_time
            ):
                continue
            trade = event.data.get("trade_result", {})
            print(f"Trade: {trade}")
        elif event.event_type == "complete":
            print(f"Final balance: {event.data.get('final_balance')}")


if __name__ == "__main__":
    asyncio.run(main())
