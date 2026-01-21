"""数据中心测试

测试交易所适配器、缓存和熔断器功能。
"""

from __future__ import annotations

import asyncio
import time
import pytest

from quanttrader.data.cache import LRUCache, DataCenterCache
from quanttrader.data.circuit_breaker import CircuitBreaker, CircuitState, CircuitBreakerOpenError
from quanttrader.data.adapters.base import ExchangeAdapter, OHLCVData


class TestLRUCache:
    """LRU 缓存测试"""

    def test_basic_get_set(self):
        cache: LRUCache[str] = LRUCache(max_size=10)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_cache_miss(self):
        cache: LRUCache[str] = LRUCache(max_size=10)
        assert cache.get("nonexistent") is None

    def test_ttl_expiration(self):
        cache: LRUCache[str] = LRUCache(max_size=10, default_ttl=0.1)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        time.sleep(0.15)
        assert cache.get("key1") is None

    def test_custom_ttl(self):
        cache: LRUCache[str] = LRUCache(max_size=10, default_ttl=10.0)
        cache.set("key1", "value1", ttl=0.1)
        assert cache.get("key1") == "value1"
        time.sleep(0.15)
        assert cache.get("key1") is None

    def test_lru_eviction(self):
        cache: LRUCache[str] = LRUCache(max_size=3)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        # 访问 key1，使其成为最近使用
        cache.get("key1")
        # 添加新项，key2 应被淘汰
        cache.set("key4", "value4")
        assert cache.get("key2") is None
        assert cache.get("key1") == "value1"
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"

    def test_hit_rate(self):
        cache: LRUCache[str] = LRUCache(max_size=10)
        cache.set("key1", "value1")
        cache.get("key1")  # hit
        cache.get("key1")  # hit
        cache.get("key2")  # miss
        assert cache.hit_rate == 2 / 3

    def test_clear_expired(self):
        cache: LRUCache[str] = LRUCache(max_size=10, default_ttl=0.1)
        cache.set("key1", "value1")
        cache.set("key2", "value2", ttl=10.0)
        time.sleep(0.15)
        cleared = cache.clear_expired()
        assert cleared == 1
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"


class TestDataCenterCache:
    """数据中心缓存测试"""

    def test_kline_cache(self):
        cache = DataCenterCache()
        data = {"ohlcv": {"close": [100, 101, 102]}}
        cache.set_kline("BTC/USDT", "1h", data)
        cached = cache.get_kline("BTC/USDT", "1h")
        assert cached == data

    def test_ticker_cache(self):
        cache = DataCenterCache(ticker_ttl=1.0)
        data = {"last_price": 50000.0}
        cache.set_ticker("BTC/USDT", data)
        assert cache.get_ticker("BTC/USDT") == data

    def test_orderbook_cache(self):
        cache = DataCenterCache()
        data = {"bids": [[50000, 1.0]], "asks": [[50001, 1.0]]}
        cache.set_orderbook("BTC/USDT", data)
        assert cache.get_orderbook("BTC/USDT") == data

    def test_stats(self):
        cache = DataCenterCache()
        cache.set_kline("BTC/USDT", "1h", {})
        stats = cache.stats()
        assert "kline" in stats
        assert "ticker" in stats
        assert "orderbook" in stats
        assert stats["kline"]["size"] == 1


class TestCircuitBreaker:
    """熔断器测试"""

    def test_initial_state_closed(self):
        cb = CircuitBreaker(failure_threshold=3)
        assert cb.state == CircuitState.CLOSED
        assert cb.allow_request() is True

    def test_open_after_failures(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.allow_request() is False

    def test_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=2, timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.allow_request() is True

    def test_close_after_success_in_half_open(self):
        cb = CircuitBreaker(failure_threshold=2, success_threshold=2, timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_reopen_on_failure_in_half_open(self):
        cb = CircuitBreaker(failure_threshold=2, timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_reset(self):
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.allow_request() is True

    def test_circuit_breaker_open_error(self):
        cb = CircuitBreaker(failure_threshold=1, name="test_breaker")
        cb.record_failure()
        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            if not cb.allow_request():
                raise CircuitBreakerOpenError(cb)
        assert "test_breaker" in str(exc_info.value)


class TestExchangeAdapter:
    """交易所适配器工具方法测试"""

    def test_normalize_symbol(self):
        assert ExchangeAdapter.normalize_symbol("BTCUSDT") == "BTC/USDT"
        assert ExchangeAdapter.normalize_symbol("BTC/USDT") == "BTC/USDT"
        assert ExchangeAdapter.normalize_symbol("ETHBTC") == "ETH/BTC"
        assert ExchangeAdapter.normalize_symbol("SOLUSDC") == "SOL/USDC"

    def test_denormalize_symbol(self):
        assert ExchangeAdapter.denormalize_symbol("BTC/USDT") == "BTCUSDT"
        assert ExchangeAdapter.denormalize_symbol("ETH/BTC") == "ETHBTC"

    def test_normalize_interval(self):
        assert ExchangeAdapter.normalize_interval("1min") == "1m"
        assert ExchangeAdapter.normalize_interval("1hour") == "1h"
        assert ExchangeAdapter.normalize_interval("1day") == "1d"
        assert ExchangeAdapter.normalize_interval("1h") == "1h"


class TestOHLCVData:
    """OHLCV 数据结构测试"""

    def test_empty(self):
        data = OHLCVData.empty()
        assert len(data) == 0
        assert data.timestamps == []

    def test_to_dict(self):
        data = OHLCVData(
            timestamps=[1000, 2000],
            open=[100.0, 101.0],
            high=[105.0, 106.0],
            low=[99.0, 100.0],
            close=[104.0, 105.0],
            volume=[1000.0, 1100.0],
        )
        d = data.to_dict()
        assert d["timestamps"] == [1000, 2000]
        assert d["close"] == [104.0, 105.0]
        assert len(data) == 2


# ==================== 集成测试（需要网络） ====================

@pytest.mark.asyncio
@pytest.mark.skip(reason="需要网络连接，手动运行")
async def test_binance_adapter_fetch_ohlcv():
    """测试 Binance 适配器获取 K 线（需要网络）"""
    from quanttrader.data.adapters.binance import BinanceAdapter
    from quanttrader.data.adapters.base import MarketType

    async with BinanceAdapter(MarketType.SPOT) as adapter:
        ohlcv = await adapter.fetch_ohlcv("BTC/USDT", "1h", limit=10)
        assert len(ohlcv) > 0
        assert ohlcv.close[-1] > 0


@pytest.mark.asyncio
@pytest.mark.skip(reason="需要网络连接，手动运行")
async def test_binance_futures_adapter():
    """测试 Binance 永续合约适配器（需要网络）"""
    from quanttrader.data.adapters.binance import BinanceAdapter
    from quanttrader.data.adapters.base import MarketType

    async with BinanceAdapter(MarketType.FUTURES) as adapter:
        ohlcv = await adapter.fetch_ohlcv("BTC/USDT", "1h", limit=10)
        assert len(ohlcv) > 0

        ticker = await adapter.fetch_ticker("BTC/USDT")
        assert ticker.last_price > 0


@pytest.mark.asyncio
@pytest.mark.skip(reason="需要网络连接，手动运行")
async def test_data_center_service():
    """测试数据中心服务（需要网络）"""
    from quanttrader.data import DataCenterService, MarketDataRequest, MarketType

    async with DataCenterService(market_type=MarketType.SPOT) as dc:
        data = await dc.get_market_data(
            MarketDataRequest(symbol="BTC/USDT", interval="1h", limit=10)
        )
        assert data["metadata"]["count"] > 0
        assert len(data["ohlcv"]["close"]) > 0

        # 测试缓存命中
        data2 = await dc.get_market_data(
            MarketDataRequest(symbol="BTC/USDT", interval="1h", limit=10)
        )
        stats = dc.cache_stats()
        assert stats["kline"]["hits"] >= 1
