"""临时测试：拉取现货 1m K 线"""

from __future__ import annotations

import asyncio

from datetime import datetime, timedelta, timezone

from quanttrader.data.adapters.base import MarketType
from quanttrader.data.base import DataCenterService, MarketDataRequest


async def main() -> None:
    now = datetime.now(timezone.utc)
    end_time = int(now.timestamp() * 1000)
    start_time = int((now - timedelta(minutes=15)).timestamp() * 1000)

    async with DataCenterService(market_type=MarketType.SPOT, enable_cache=False) as dc:
        data = await dc.get_market_data(
            MarketDataRequest(
                symbol="BTC/USDT",
                interval="1m",
                limit=20,
                start_time=start_time,
                end_time=end_time,
            )
        )

    ohlcv = data.get("ohlcv", {})
    closes = ohlcv.get("close", [])
    timestamps = ohlcv.get("timestamps", [])

    local_tz = timezone(timedelta(hours=8))

    print(f"现货 1m K 线数量: {len(closes)}")
    for ts, close in zip(timestamps, closes):
        ts_dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).astimezone(local_tz)
        print(f"{ts_dt.strftime('%Y-%m-%d %H:%M')} +08:00 | close: {close}")


if __name__ == "__main__":
    asyncio.run(main())
