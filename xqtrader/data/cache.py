"""数据缓存层

提供 K 线数据、行情数据的缓存机制，支持 TTL 过期和 LRU 淘汰。
"""

from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Dict, Generic, Optional, TypeVar

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    """缓存条目"""

    data: T
    timestamp: float
    ttl: float

    def is_expired(self) -> bool:
        return time.time() - self.timestamp > self.ttl


class LRUCache(Generic[T]):
    """LRU 缓存实现

    支持：
    - TTL 过期
    - 最大容量限制
    - LRU 淘汰策略
    """

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: float = 300.0,
    ) -> None:
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry[T]] = OrderedDict()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[T]:
        """获取缓存数据"""
        if key not in self._cache:
            self._misses += 1
            return None

        entry = self._cache[key]

        if entry.is_expired():
            del self._cache[key]
            self._misses += 1
            return None

        # 移到末尾（最近访问）
        self._cache.move_to_end(key)
        self._hits += 1
        return entry.data

    def set(self, key: str, data: T, ttl: Optional[float] = None) -> None:
        """设置缓存数据"""
        if key in self._cache:
            del self._cache[key]

        # 检查容量，淘汰最旧的
        while len(self._cache) >= self.max_size:
            self._cache.popitem(last=False)

        self._cache[key] = CacheEntry(
            data=data,
            timestamp=time.time(),
            ttl=ttl or self.default_ttl,
        )

    def delete(self, key: str) -> bool:
        """删除缓存条目"""
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def clear_expired(self) -> int:
        """清除过期条目，返回清除数量"""
        expired_keys = [
            key for key, entry in self._cache.items() if entry.is_expired()
        ]
        for key in expired_keys:
            del self._cache[key]
        return len(expired_keys)

    @property
    def size(self) -> int:
        return len(self._cache)

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        return {
            "size": self.size,
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self.hit_rate,
        }


class DataCenterCache:
    """数据中心缓存管理器

    为不同类型的数据维护独立的缓存：
    - K 线缓存（较长 TTL）
    - 行情缓存（较短 TTL）
    - 订单簿缓存（很短 TTL）
    """

    def __init__(
        self,
        kline_ttl: float = 60.0,
        ticker_ttl: float = 5.0,
        orderbook_ttl: float = 1.0,
        max_size: int = 1000,
    ) -> None:
        self.kline_cache: LRUCache[Dict[str, Any]] = LRUCache(
            max_size=max_size, default_ttl=kline_ttl
        )
        self.ticker_cache: LRUCache[Dict[str, Any]] = LRUCache(
            max_size=max_size // 2, default_ttl=ticker_ttl
        )
        self.orderbook_cache: LRUCache[Dict[str, Any]] = LRUCache(
            max_size=max_size // 4, default_ttl=orderbook_ttl
        )

    def _kline_key(
        self,
        symbol: str,
        interval: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 100,
    ) -> str:
        """生成 K 线缓存键"""
        return f"kline:{symbol}:{interval}:{start_time}:{end_time}:{limit}"

    def get_kline(
        self,
        symbol: str,
        interval: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 100,
    ) -> Optional[Dict[str, Any]]:
        """获取 K 线缓存"""
        key = self._kline_key(symbol, interval, start_time, end_time, limit)
        return self.kline_cache.get(key)

    def set_kline(
        self,
        symbol: str,
        interval: str,
        data: Dict[str, Any],
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 100,
        ttl: Optional[float] = None,
    ) -> None:
        """设置 K 线缓存"""
        key = self._kline_key(symbol, interval, start_time, end_time, limit)
        self.kline_cache.set(key, data, ttl)

    def get_ticker(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取行情缓存"""
        return self.ticker_cache.get(f"ticker:{symbol}")

    def set_ticker(
        self, symbol: str, data: Dict[str, Any], ttl: Optional[float] = None
    ) -> None:
        """设置行情缓存"""
        self.ticker_cache.set(f"ticker:{symbol}", data, ttl)

    def get_orderbook(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取订单簿缓存"""
        return self.orderbook_cache.get(f"orderbook:{symbol}")

    def set_orderbook(
        self, symbol: str, data: Dict[str, Any], ttl: Optional[float] = None
    ) -> None:
        """设置订单簿缓存"""
        self.orderbook_cache.set(f"orderbook:{symbol}", data, ttl)

    def clear_all(self) -> None:
        """清空所有缓存"""
        self.kline_cache.clear()
        self.ticker_cache.clear()
        self.orderbook_cache.clear()

    def stats(self) -> Dict[str, Any]:
        """获取所有缓存统计"""
        return {
            "kline": self.kline_cache.stats(),
            "ticker": self.ticker_cache.stats(),
            "orderbook": self.orderbook_cache.stats(),
        }
