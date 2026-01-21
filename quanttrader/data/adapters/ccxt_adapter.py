"""基于 CCXT 的通用交易所适配器

使用 ccxt 库实现统一的交易所接口，支持 100+ 交易所。
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from quanttrader.data.adapters.base import (
    ExchangeAdapter,
    MarketType,
    OHLCVData,
    OrderBookData,
    TickerData,
)

try:
    import ccxt.async_support as ccxt_async
    import ccxt

    CCXT_AVAILABLE = True
except ImportError:
    CCXT_AVAILABLE = False
    ccxt_async = None
    ccxt = None


class CCXTAdapter(ExchangeAdapter):
    """基于 CCXT 的通用交易所适配器

    支持所有 CCXT 支持的交易所，通过 exchange_id 指定。

    Example:
        async with CCXTAdapter("binance", MarketType.FUTURES) as adapter:
            ohlcv = await adapter.fetch_ohlcv("BTC/USDT", "1h", limit=100)
    """

    # CCXT 支持的时间间隔映射
    INTERVAL_MAP = {
        "1m": "1m",
        "3m": "3m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "1h",
        "2h": "2h",
        "4h": "4h",
        "6h": "6h",
        "8h": "8h",
        "12h": "12h",
        "1d": "1d",
        "3d": "3d",
        "1w": "1w",
        "1M": "1M",
    }

    def __init__(
        self,
        exchange_id: str = "binance",
        market_type: MarketType = MarketType.SPOT,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        sandbox: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(exchange_id, market_type, api_key, api_secret, sandbox)

        if not CCXT_AVAILABLE:
            raise ImportError(
                "ccxt is required for CCXTAdapter. Install with: pip install ccxt"
            )

        self._exchange: Optional[ccxt_async.Exchange] = None
        self._extra_config = kwargs

    def _get_exchange_class(self) -> type:
        """获取对应的 CCXT 交易所类"""
        exchange_id = self.exchange_id.lower()

        # 处理合约市场
        if self.market_type == MarketType.FUTURES:
            # Binance USDT-M 使用 binanceusdm
            if exchange_id == "binance":
                exchange_id = "binanceusdm"
            elif exchange_id == "okx":
                exchange_id = "okx"  # OKX 统一接口
            elif exchange_id == "bybit":
                exchange_id = "bybit"
        elif self.market_type == MarketType.DELIVERY:
            if exchange_id == "binance":
                exchange_id = "binancecoinm"

        if not hasattr(ccxt_async, exchange_id):
            raise ValueError(f"Unsupported exchange: {exchange_id}")

        return getattr(ccxt_async, exchange_id)

    async def connect(self) -> None:
        """初始化 CCXT 交易所客户端"""
        exchange_class = self._get_exchange_class()

        config: Dict[str, Any] = {
            "enableRateLimit": True,  # 启用限速
            "timeout": 30000,  # 30 秒超时
        }

        if self.api_key:
            config["apiKey"] = self.api_key
        if self.api_secret:
            config["secret"] = self.api_secret
        if self.sandbox:
            config["sandbox"] = True

        # 合并额外配置
        config.update(self._extra_config)

        self._exchange = exchange_class(config)

        # 加载市场信息
        await self._exchange.load_markets()

    async def close(self) -> None:
        """关闭 CCXT 客户端"""
        if self._exchange:
            await self._exchange.close()
            self._exchange = None

    @property
    def exchange(self) -> ccxt_async.Exchange:
        """获取底层 CCXT 交易所实例"""
        if self._exchange is None:
            raise RuntimeError("Adapter not connected. Use 'async with' or call connect() first.")
        return self._exchange

    async def fetch_ohlcv(
        self,
        symbol: str,
        interval: str,
        limit: int = 100,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> OHLCVData:
        """获取 K 线数据"""
        normalized_symbol = self.normalize_symbol(symbol, self.market_type)
        timeframe = self.INTERVAL_MAP.get(interval, interval)

        # CCXT fetch_ohlcv 参数
        params: Dict[str, Any] = {}
        if end_time:
            params["until"] = end_time

        try:
            # CCXT 返回格式: [[timestamp, open, high, low, close, volume], ...]
            ohlcv = await self.exchange.fetch_ohlcv(
                normalized_symbol,
                timeframe=timeframe,
                since=start_time,
                limit=limit,
                params=params,
            )

            if not ohlcv:
                return OHLCVData.empty()

            return OHLCVData(
                timestamps=[int(candle[0]) for candle in ohlcv],
                open=[float(candle[1]) for candle in ohlcv],
                high=[float(candle[2]) for candle in ohlcv],
                low=[float(candle[3]) for candle in ohlcv],
                close=[float(candle[4]) for candle in ohlcv],
                volume=[float(candle[5]) for candle in ohlcv],
            )
        except ccxt.NetworkError as e:
            raise ConnectionError(f"Network error fetching OHLCV: {e}") from e
        except ccxt.ExchangeError as e:
            raise ValueError(f"Exchange error fetching OHLCV: {e}") from e

    async def fetch_ticker(self, symbol: str) -> TickerData:
        """获取最新行情"""
        normalized_symbol = self.normalize_symbol(symbol, self.market_type)

        try:
            ticker = await self.exchange.fetch_ticker(normalized_symbol)

            # CCXT 在顶层提供 markPrice 和 indexPrice（合约专用）
            mark_price = ticker.get("markPrice")
            index_price = ticker.get("indexPrice")

            return TickerData(
                symbol=normalized_symbol,
                last_price=float(ticker.get("last") or 0),
                bid_price=float(ticker.get("bid") or 0),
                ask_price=float(ticker.get("ask") or 0),
                volume_24h=float(ticker.get("quoteVolume") or ticker.get("baseVolume") or 0),
                timestamp=int(ticker.get("timestamp") or 0),
                mark_price=float(mark_price) if mark_price else None,
                index_price=float(index_price) if index_price else None,
                funding_rate=None,  # 需要单独获取
            )
        except ccxt.NetworkError as e:
            raise ConnectionError(f"Network error fetching ticker: {e}") from e
        except ccxt.ExchangeError as e:
            raise ValueError(f"Exchange error fetching ticker: {e}") from e

    async def fetch_order_book(
        self, symbol: str, limit: int = 20
    ) -> OrderBookData:
        """获取订单簿"""
        normalized_symbol = self.normalize_symbol(symbol, self.market_type)

        try:
            order_book = await self.exchange.fetch_order_book(
                normalized_symbol, limit=limit
            )

            return OrderBookData(
                symbol=normalized_symbol,
                bids=[[float(b[0]), float(b[1])] for b in order_book.get("bids", [])],
                asks=[[float(a[0]), float(a[1])] for a in order_book.get("asks", [])],
                timestamp=int(order_book.get("timestamp", 0)),
            )
        except ccxt.NetworkError as e:
            raise ConnectionError(f"Network error fetching order book: {e}") from e
        except ccxt.ExchangeError as e:
            raise ValueError(f"Exchange error fetching order book: {e}") from e

    async def fetch_ohlcv_batch(
        self,
        symbol: str,
        interval: str,
        start_time: int,
        end_time: int,
        batch_size: int = 1000,
    ) -> OHLCVData:
        """批量获取历史 K 线数据

        自动分批请求，合并结果。
        """
        all_data = OHLCVData.empty()
        current_start = start_time

        # 计算时间间隔毫秒数
        interval_ms = self._interval_to_ms(interval)

        while current_start < end_time:
            batch = await self.fetch_ohlcv(
                symbol,
                interval,
                limit=batch_size,
                start_time=current_start,
                end_time=end_time,
            )

            if len(batch) == 0:
                break

            # 合并数据
            all_data.timestamps.extend(batch.timestamps)
            all_data.open.extend(batch.open)
            all_data.high.extend(batch.high)
            all_data.low.extend(batch.low)
            all_data.close.extend(batch.close)
            all_data.volume.extend(batch.volume)

            # 更新起始时间
            last_timestamp = batch.timestamps[-1]
            current_start = last_timestamp + interval_ms

            # 避免触发限速
            await asyncio.sleep(0.1)

        return all_data

    @staticmethod
    def _interval_to_ms(interval: str) -> int:
        """将时间间隔转换为毫秒"""
        multipliers = {
            "m": 60 * 1000,
            "h": 60 * 60 * 1000,
            "d": 24 * 60 * 60 * 1000,
            "w": 7 * 24 * 60 * 60 * 1000,
            "M": 30 * 24 * 60 * 60 * 1000,
        }
        unit = interval[-1]
        value = int(interval[:-1])
        return value * multipliers.get(unit, 60 * 1000)

    def get_supported_intervals(self) -> list:
        """获取交易所支持的时间间隔"""
        if self._exchange and hasattr(self._exchange, "timeframes"):
            return list(self._exchange.timeframes.keys())
        return list(self.INTERVAL_MAP.keys())
