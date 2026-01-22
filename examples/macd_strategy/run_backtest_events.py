"""MACD 事件合约回测示例"""

from __future__ import annotations

import asyncio

from datetime import datetime, timedelta, timezone

from quanttrader.engine.backtest import BacktestConfig, BacktestEngine
from macd_strategy import MACDConfig, MACDStrategy


async def main() -> None:
    macd_config = MACDConfig(
        timeframe="5m",
        require_histogram_confirm=False,
    )
    strategy = MACDStrategy(config=macd_config)

    engine = BacktestEngine()
    now = datetime.now(timezone.utc)
    last_closed = now.replace(minute=0, second=0, microsecond=0)
    if last_closed > now:
        last_closed -= timedelta(hours=1)
    end_time = int(last_closed.timestamp() * 1000)
    start_time = int((last_closed - timedelta(hours=3)).timestamp() * 1000)

    requested_start_time = start_time
    requested_end_time = end_time

    config = BacktestConfig(
        symbol="BTC/USDT",
        interval="1m",
        initial_capital=10000.0,
        start_time=start_time,
        end_time=end_time,
        contract_type="events",
        enable_cache=False,
    )

    indicator_id = f"macd_{macd_config.timeframe}"
    warmed_up = False

    local_tz = datetime.now().astimezone().tzinfo

    signal_count = 0
    latest_macd = {}

    async for event in engine.run(strategy, config):
        if event.event_type == "tick":
            indicators = event.data.get("incremental_indicators", {})
            timeframe_state = indicators.get("by_timeframe", {}).get(macd_config.timeframe, {})
            is_warmed_up = timeframe_state.get("is_warmed_up", indicators.get("is_warmed_up", False))
            warmed_up = is_warmed_up

            macd_data = indicators.get("macd", {}).get(indicator_id, {})
            if macd_data:
                latest_macd = macd_data

        elif event.event_type == "trade":
            trade_bar = event.data.get("bar", {})
            trade_ts = trade_bar.get("timestamp")
            record = event.data.get("record")

            if not record:
                continue

            if record.get("skipped") is True:
                continue

            if (
                not warmed_up
                or (isinstance(trade_ts, int) and trade_ts > 0 and trade_ts < requested_start_time)
                or (isinstance(trade_ts, int) and trade_ts > 0 and trade_ts > requested_end_time)
            ):
                continue

            signal_count += 1
            trade_result = event.data.get("trade_result", {})
            trade_time = datetime.fromtimestamp(trade_ts / 1000).astimezone(local_tz)

            action = record.get("action", "N/A")
            pnl = trade_result.get("pnl", 0.0)
            win = record.get("win")

            macd_val = latest_macd.get("macd")
            signal_val = latest_macd.get("signal_line")
            hist_val = latest_macd.get("histogram")

            macd_str = f"{macd_val:.4f}" if isinstance(macd_val, (int, float)) else "N/A"
            signal_str = f"{signal_val:.4f}" if isinstance(signal_val, (int, float)) else "N/A"
            hist_str = f"{hist_val:.4f}" if isinstance(hist_val, (int, float)) else "N/A"
            win_str = "赢" if win is True else "输" if win is False else "N/A"

            print(
                f"\nSignal #{signal_count} | {trade_time.strftime('%Y-%m-%d %H:%M')}\n"
                f"   Action: {action}\n"
                f"   Price: {trade_bar.get('close')}\n"
                f"   Result: {win_str} | PnL: {pnl:.2f}\n"
                f"   MACD: {macd_str} | Signal: {signal_str} | Hist: {hist_str}"
            )

        elif event.event_type == "complete":
            print(f"\n{'='*50}")
            print(f"回测完成 | 总信号数: {signal_count} | 最终余额: {event.data.get('final_balance')}")


if __name__ == "__main__":
    asyncio.run(main())
