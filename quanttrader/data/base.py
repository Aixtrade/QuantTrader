"""数据中心服务

统一数据获取入口，整合：
- 交易所适配器（CCXT/Binance）
- 缓存层（LRU + TTL）
- 熔断器（故障保护）
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Type

from quanttrader.data.adapters.base import (
    ExchangeAdapter,
    MarketType,
    OHLCVData,
    OrderBookData,
    TickerData,
)
from quanttrader.data.adapters.ccxt_adapter import CCXTAdapter, CCXT_AVAILABLE
from quanttrader.data.adapters.binance import BinanceAdapter
from quanttrader.data.cache import DataCenterCache
from quanttrader.data.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError


@dataclass
class MarketDataRequest:
    """市场数据请求"""

    symbol: str
    interval: str
    exchange: str = "binance"
    market_type: str = "spot"  # spot | futures | delivery
    limit: int = 100
    start_time: Optional[int] = None
    end_time: Optional[int] = None


class DataCenterService:
    """数据中心服务 - 统一数据获取入口

    特性：
    - 多交易所支持（通过 CCXT）
    - 自动缓存（可配置 TTL）
    - 熔断保护（失败自动熔断）
    - 支持现货和合约市场

    Example:
        # 基础用法
        async with DataCenterService() as dc:
            data = await dc.get_market_data(
                MarketDataRequest(symbol="BTC/USDT", interval="1h")
            )

        # 永续合约
        async with DataCenterService(market_type=MarketType.FUTURES) as dc:
            data = await dc.get_market_data(
                MarketDataRequest(symbol="BTC/USDT", interval="1h", market_type="futures")
            )
    """

    # 支持的交易所映射
    EXCHANGE_ADAPTERS: Dict[str, Type[ExchangeAdapter]] = {
        "binance": BinanceAdapter,
        # 未来扩展
        # "okx": OKXAdapter,
        # "bybit": BybitAdapter,
    }

    def __init__(
        self,
        exchange: str = "binance",
        market_type: MarketType = MarketType.SPOT,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        enable_cache: bool = True,
        cache_ttl: float = 60.0,
        enable_circuit_breaker: bool = True,
        sandbox: bool = False,
    ) -> None:
        self.exchange_id = exchange.lower()
        self.market_type = market_type
        self.api_key = api_key
        self.api_secret = api_secret
        self.sandbox = sandbox

        # 缓存
        self._cache: Optional[DataCenterCache] = None
        if enable_cache:
            self._cache = DataCenterCache(kline_ttl=cache_ttl)

        # 熔断器
        self._circuit_breaker: Optional[CircuitBreaker] = None
        if enable_circuit_breaker:
            self._circuit_breaker = CircuitBreaker(
                name=f"{exchange}_{market_type.value}",
                failure_threshold=5,
                timeout=30.0,
            )

        # 适配器实例
        self._adapter: Optional[ExchangeAdapter] = None

    def _get_adapter_class(self) -> Type[ExchangeAdapter]:
        """获取适配器类"""
        if self.exchange_id in self.EXCHANGE_ADAPTERS:
            return self.EXCHANGE_ADAPTERS[self.exchange_id]
        # 通用 CCXT 适配器
        return CCXTAdapter

    async def connect(self) -> None:
        """建立连接"""
        if not CCXT_AVAILABLE:
            raise ImportError(
                "ccxt is required. Install with: pip install ccxt"
            )

        adapter_class = self._get_adapter_class()

        if adapter_class == BinanceAdapter:
            self._adapter = BinanceAdapter(
                market_type=self.market_type,
                api_key=self.api_key,
                api_secret=self.api_secret,
                sandbox=self.sandbox,
            )
        else:
            self._adapter = CCXTAdapter(
                exchange_id=self.exchange_id,
                market_type=self.market_type,
                api_key=self.api_key,
                api_secret=self.api_secret,
                sandbox=self.sandbox,
            )

        await self._adapter.connect()

    async def close(self) -> None:
        """关闭连接"""
        if self._adapter:
            await self._adapter.close()
            self._adapter = None

    async def __aenter__(self) -> "DataCenterService":
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    @property
    def adapter(self) -> ExchangeAdapter:
        """获取底层适配器"""
        if self._adapter is None:
            raise RuntimeError("DataCenterService not connected")
        return self._adapter

    def _check_circuit_breaker(self) -> None:
        """检查熔断器状态"""
        if self._circuit_breaker and not self._circuit_breaker.allow_request():
            raise CircuitBreakerOpenError(self._circuit_breaker)

    def _record_success(self) -> None:
        """记录成功"""
        if self._circuit_breaker:
            self._circuit_breaker.record_success()

    def _record_failure(self) -> None:
        """记录失败"""
        if self._circuit_breaker:
            self._circuit_breaker.record_failure()

    async def get_market_data(
        self, request: MarketDataRequest
    ) -> Dict[str, Any]:
        """获取市场数据（带缓存）

        返回格式：
        {
            "ohlcv": {
                "open": [...], "high": [...], "low": [...],
                "close": [...], "volume": [...], "timestamps": [...]
            },
            "metadata": {
                "symbol": "...",
                "interval": "...",
                "count": 100,
                "exchange": "binance"
            }
        }
        """
        symbol = ExchangeAdapter.normalize_symbol(request.symbol)

        # 尝试从缓存获取
        if self._cache:
            cached = self._cache.get_kline(
                symbol,
                request.interval,
                request.start_time,
                request.end_time,
                request.limit,
            )
            if cached:
                return cached

        # 检查熔断器
        self._check_circuit_breaker()

        try:
            ohlcv = await self.adapter.fetch_ohlcv(
                symbol,
                request.interval,
                limit=request.limit,
                start_time=request.start_time,
                end_time=request.end_time,
            )

            result = {
                "ohlcv": ohlcv.to_dict(),
                "metadata": {
                    "symbol": symbol,
                    "interval": request.interval,
                    "count": len(ohlcv),
                    "exchange": self.exchange_id,
                    "market_type": self.market_type.value,
                },
            }

            # 缓存结果
            if self._cache:
                self._cache.set_kline(
                    symbol,
                    request.interval,
                    result,
                    request.start_time,
                    request.end_time,
                    request.limit,
                )

            self._record_success()
            return result

        except Exception as e:
            self._record_failure()
            raise

    async def get_historical_klines_batch(
        self,
        request: MarketDataRequest,
        batch_size: int = 1000,
    ) -> Dict[str, Any]:
        """批量获取历史 K 线数据"""
        if not request.start_time or not request.end_time:
            raise ValueError("start_time and end_time required for batch fetch")

        self._check_circuit_breaker()

        try:
            if isinstance(self.adapter, CCXTAdapter):
                ohlcv = await self.adapter.fetch_ohlcv_batch(
                    request.symbol,
                    request.interval,
                    request.start_time,
                    request.end_time,
                    batch_size=batch_size,
                )
            else:
                ohlcv = await self.adapter.fetch_ohlcv(
                    request.symbol,
                    request.interval,
                    limit=request.limit,
                    start_time=request.start_time,
                    end_time=request.end_time,
                )

            self._record_success()

            return {
                "ohlcv": ohlcv.to_dict(),
                "metadata": {
                    "symbol": request.symbol,
                    "interval": request.interval,
                    "count": len(ohlcv),
                    "exchange": self.exchange_id,
                },
            }
        except Exception as e:
            self._record_failure()
            raise

    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """获取最新行情"""
        symbol = ExchangeAdapter.normalize_symbol(symbol)

        # 尝试从缓存获取
        if self._cache:
            cached = self._cache.get_ticker(symbol)
            if cached:
                return cached

        self._check_circuit_breaker()

        try:
            ticker = await self.adapter.fetch_ticker(symbol)
            result = {
                "symbol": ticker.symbol,
                "last_price": ticker.last_price,
                "bid_price": ticker.bid_price,
                "ask_price": ticker.ask_price,
                "volume_24h": ticker.volume_24h,
                "timestamp": ticker.timestamp,
                "mark_price": ticker.mark_price,
                "index_price": ticker.index_price,
                "funding_rate": ticker.funding_rate,
            }

            if self._cache:
                self._cache.set_ticker(symbol, result)

            self._record_success()
            return result

        except Exception as e:
            self._record_failure()
            raise

    async def get_order_book(
        self, symbol: str, limit: int = 20
    ) -> Dict[str, Any]:
        """获取订单簿"""
        symbol = ExchangeAdapter.normalize_symbol(symbol)

        if self._cache:
            cached = self._cache.get_orderbook(symbol)
            if cached:
                return cached

        self._check_circuit_breaker()

        try:
            order_book = await self.adapter.fetch_order_book(symbol, limit)
            result = {
                "symbol": order_book.symbol,
                "bids": order_book.bids,
                "asks": order_book.asks,
                "timestamp": order_book.timestamp,
            }

            if self._cache:
                self._cache.set_orderbook(symbol, result)

            self._record_success()
            return result

        except Exception as e:
            self._record_failure()
            raise

    def cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        if self._cache:
            return self._cache.stats()
        return {}

    def circuit_breaker_stats(self) -> Dict[str, Any]:
        """获取熔断器统计"""
        if self._circuit_breaker:
            stats = self._circuit_breaker.stats()
            return {
                "state": stats.state.value,
                "failure_count": stats.failure_count,
                "success_count": stats.success_count,
            }
        return {}
