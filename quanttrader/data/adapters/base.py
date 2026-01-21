"""交易所适配器抽象基类

定义统一的交易所接口，支持多交易所扩展。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class MarketType(str, Enum):
    """市场类型"""

    SPOT = "spot"
    FUTURES = "futures"  # USDT-M 永续
    DELIVERY = "delivery"  # COIN-M 交割


@dataclass
class OHLCVData:
    """标准化 OHLCV 数据结构"""

    timestamps: List[int]  # 毫秒时间戳
    open: List[float]
    high: List[float]
    low: List[float]
    close: List[float]
    volume: List[float]

    def __len__(self) -> int:
        return len(self.timestamps)

    def to_dict(self) -> Dict[str, List[float]]:
        return {
            "timestamps": self.timestamps,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }

    @classmethod
    def empty(cls) -> "OHLCVData":
        return cls(
            timestamps=[],
            open=[],
            high=[],
            low=[],
            close=[],
            volume=[],
        )


@dataclass
class TickerData:
    """行情数据"""

    symbol: str
    last_price: float
    bid_price: float
    ask_price: float
    volume_24h: float
    timestamp: int
    # 合约特有字段
    mark_price: Optional[float] = None
    index_price: Optional[float] = None
    funding_rate: Optional[float] = None


@dataclass
class OrderBookData:
    """订单簿数据"""

    symbol: str
    bids: List[List[float]]  # [[price, amount], ...]
    asks: List[List[float]]  # [[price, amount], ...]
    timestamp: int


class ExchangeAdapter(ABC):
    """交易所适配器抽象基类

    统一接口设计，支持：
    - 多交易所切换（Binance, OKX, Bybit 等）
    - 多市场类型（现货、U本位合约、币本位合约）
    - 同步/异步调用
    """

    def __init__(
        self,
        exchange_id: str,
        market_type: MarketType = MarketType.SPOT,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        sandbox: bool = False,
    ) -> None:
        self.exchange_id = exchange_id
        self.market_type = market_type
        self.api_key = api_key
        self.api_secret = api_secret
        self.sandbox = sandbox

    @abstractmethod
    async def connect(self) -> None:
        """建立连接（初始化客户端）"""

    @abstractmethod
    async def close(self) -> None:
        """关闭连接"""

    async def __aenter__(self) -> "ExchangeAdapter":
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    # ==================== 市场数据 API ====================

    @abstractmethod
    async def fetch_ohlcv(
        self,
        symbol: str,
        interval: str,
        limit: int = 100,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> OHLCVData:
        """获取 K 线数据

        Args:
            symbol: 交易对，统一格式 "BTC/USDT"
            interval: K线周期 (1m, 5m, 15m, 1h, 4h, 1d)
            limit: 数据条数
            start_time: 开始时间（毫秒时间戳）
            end_time: 结束时间（毫秒时间戳）

        Returns:
            标准化的 OHLCV 数据
        """

    @abstractmethod
    async def fetch_ticker(self, symbol: str) -> TickerData:
        """获取最新行情"""

    @abstractmethod
    async def fetch_order_book(
        self, symbol: str, limit: int = 20
    ) -> OrderBookData:
        """获取订单簿"""

    async def fetch_mark_price(self, symbol: str) -> Optional[float]:
        """获取标记价格（合约专用）"""
        ticker = await self.fetch_ticker(symbol)
        return ticker.mark_price

    async def fetch_funding_rate(self, symbol: str) -> Optional[float]:
        """获取资金费率（合约专用）"""
        ticker = await self.fetch_ticker(symbol)
        return ticker.funding_rate

    # ==================== 工具方法 ====================

    @staticmethod
    def normalize_symbol(symbol: str, market_type: Optional["MarketType"] = None) -> str:
        """标准化交易对格式

        现货: BTCUSDT -> BTC/USDT
        永续: BTCUSDT -> BTC/USDT:USDT (CCXT 格式)
        """
        # 已经是标准格式
        if ":" in symbol:
            return symbol.upper()

        base_symbol = symbol.upper()

        # 处理已有斜杠的格式
        if "/" in base_symbol:
            if market_type in (MarketType.FUTURES, MarketType.DELIVERY):
                # 永续合约需要加后缀
                parts = base_symbol.split("/")
                if len(parts) == 2:
                    return f"{parts[0]}/{parts[1]}:{parts[1]}"
            return base_symbol

        # 解析无斜杠格式
        for quote in ["USDT", "USDC", "BUSD", "USD", "BTC", "ETH"]:
            if base_symbol.endswith(quote):
                base = base_symbol[: -len(quote)]
                if market_type in (MarketType.FUTURES, MarketType.DELIVERY):
                    return f"{base}/{quote}:{quote}"
                return f"{base}/{quote}"

        return base_symbol

    @staticmethod
    def denormalize_symbol(symbol: str, exchange_id: str = "binance") -> str:
        """反标准化: BTC/USDT -> BTCUSDT"""
        return symbol.replace("/", "")

    @staticmethod
    def normalize_interval(interval: str) -> str:
        """标准化时间间隔"""
        mapping = {
            "1min": "1m",
            "5min": "5m",
            "15min": "15m",
            "30min": "30m",
            "60min": "1h",
            "1hour": "1h",
            "4hour": "4h",
            "1day": "1d",
            "1week": "1w",
        }
        return mapping.get(interval.lower(), interval.lower())
