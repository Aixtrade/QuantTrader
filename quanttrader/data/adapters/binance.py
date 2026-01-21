"""Binance 交易所适配器

继承 CCXTAdapter，添加 Binance 特有功能：
- 标记价格/指数价格 K 线
- 资金费率历史
- 持仓信息
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from quanttrader.data.adapters.base import MarketType, OHLCVData
from quanttrader.data.adapters.ccxt_adapter import CCXTAdapter, CCXT_AVAILABLE

if CCXT_AVAILABLE:
    import ccxt.async_support as ccxt_async
    import ccxt


@dataclass
class FundingRateData:
    """资金费率数据"""

    symbol: str
    funding_rate: float
    funding_time: int
    mark_price: Optional[float] = None


@dataclass
class PositionData:
    """持仓数据"""

    symbol: str
    side: str  # "long" | "short"
    size: float
    entry_price: float
    mark_price: float
    unrealized_pnl: float
    leverage: int
    liquidation_price: float
    margin_type: str  # "isolated" | "cross"


class BinanceAdapter(CCXTAdapter):
    """Binance 专用适配器

    在 CCXTAdapter 基础上增加：
    - 标记价格 K 线 (markPriceKlines)
    - 指数价格 K 线 (indexPriceKlines)
    - 资金费率历史 (fundingRateHistory)
    - Premium Index K 线

    Example:
        # 现货
        async with BinanceAdapter(MarketType.SPOT) as adapter:
            ohlcv = await adapter.fetch_ohlcv("BTC/USDT", "1h")

        # U 本位永续
        async with BinanceAdapter(MarketType.FUTURES) as adapter:
            ohlcv = await adapter.fetch_ohlcv("BTC/USDT", "1h")
            mark_klines = await adapter.fetch_mark_price_klines("BTC/USDT", "1h")
    """

    def __init__(
        self,
        market_type: MarketType = MarketType.SPOT,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        sandbox: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            exchange_id="binance",
            market_type=market_type,
            api_key=api_key,
            api_secret=api_secret,
            sandbox=sandbox,
            **kwargs,
        )

    async def fetch_mark_price_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 100,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> OHLCVData:
        """获取标记价格 K 线（仅合约）

        Binance API: GET /fapi/v1/markPriceKlines
        """
        if self.market_type == MarketType.SPOT:
            raise ValueError("Mark price klines are only available for futures")

        normalized_symbol = self.normalize_symbol(symbol)
        binance_symbol = self.denormalize_symbol(normalized_symbol)
        timeframe = self.INTERVAL_MAP.get(interval, interval)

        params: Dict[str, Any] = {
            "symbol": binance_symbol,
            "interval": timeframe,
            "limit": limit,
        }
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        try:
            # 使用 ccxt 的 fapiPublicGetMarkPriceKlines 方法
            response = await self.exchange.fapiPublicGetMarkPriceKlines(params)

            if not response:
                return OHLCVData.empty()

            return OHLCVData(
                timestamps=[int(candle[0]) for candle in response],
                open=[float(candle[1]) for candle in response],
                high=[float(candle[2]) for candle in response],
                low=[float(candle[3]) for candle in response],
                close=[float(candle[4]) for candle in response],
                volume=[0.0 for _ in response],  # 标记价格无成交量
            )
        except Exception as e:
            raise ValueError(f"Error fetching mark price klines: {e}") from e

    async def fetch_index_price_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 100,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> OHLCVData:
        """获取指数价格 K 线（仅合约）

        Binance API: GET /fapi/v1/indexPriceKlines
        """
        if self.market_type == MarketType.SPOT:
            raise ValueError("Index price klines are only available for futures")

        normalized_symbol = self.normalize_symbol(symbol)
        binance_symbol = self.denormalize_symbol(normalized_symbol)
        # 指数符号通常没有 USDT 后缀，但 API 需要 pair 参数
        timeframe = self.INTERVAL_MAP.get(interval, interval)

        params: Dict[str, Any] = {
            "pair": binance_symbol.replace("USDT", ""),  # BTCUSDT -> BTC
            "interval": timeframe,
            "limit": limit,
        }
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        try:
            response = await self.exchange.fapiPublicGetIndexPriceKlines(params)

            if not response:
                return OHLCVData.empty()

            return OHLCVData(
                timestamps=[int(candle[0]) for candle in response],
                open=[float(candle[1]) for candle in response],
                high=[float(candle[2]) for candle in response],
                low=[float(candle[3]) for candle in response],
                close=[float(candle[4]) for candle in response],
                volume=[0.0 for _ in response],
            )
        except Exception as e:
            raise ValueError(f"Error fetching index price klines: {e}") from e

    async def fetch_funding_rate_history(
        self,
        symbol: str,
        limit: int = 100,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> List[FundingRateData]:
        """获取历史资金费率

        Binance API: GET /fapi/v1/fundingRate
        """
        if self.market_type == MarketType.SPOT:
            raise ValueError("Funding rate is only available for futures")

        normalized_symbol = self.normalize_symbol(symbol, self.market_type)

        try:
            # ccxt 提供的方法
            funding_history = await self.exchange.fetch_funding_rate_history(
                normalized_symbol,
                since=start_time,
                limit=limit,
                params={"endTime": end_time} if end_time else {},
            )

            return [
                FundingRateData(
                    symbol=normalized_symbol,
                    funding_rate=float(item.get("fundingRate", 0)),
                    funding_time=int(item.get("timestamp", 0)),
                    mark_price=item.get("markPrice"),
                )
                for item in funding_history
            ]
        except Exception as e:
            raise ValueError(f"Error fetching funding rate history: {e}") from e

    async def fetch_current_funding_rate(self, symbol: str) -> FundingRateData:
        """获取当前资金费率"""
        if self.market_type == MarketType.SPOT:
            raise ValueError("Funding rate is only available for futures")

        normalized_symbol = self.normalize_symbol(symbol, self.market_type)

        try:
            funding = await self.exchange.fetch_funding_rate(normalized_symbol)

            return FundingRateData(
                symbol=normalized_symbol,
                funding_rate=float(funding.get("fundingRate", 0)),
                funding_time=int(funding.get("fundingTimestamp", 0)),
                mark_price=float(funding.get("markPrice", 0)) if funding.get("markPrice") else None,
            )
        except Exception as e:
            raise ValueError(f"Error fetching current funding rate: {e}") from e

    async def fetch_positions(self) -> List[PositionData]:
        """获取所有持仓（需要 API 密钥）"""
        if self.market_type == MarketType.SPOT:
            raise ValueError("Positions are only available for futures")

        if not self.api_key:
            raise ValueError("API key required for fetching positions")

        try:
            positions = await self.exchange.fetch_positions()

            return [
                PositionData(
                    symbol=pos["symbol"],
                    side="long" if float(pos.get("contracts", 0)) > 0 else "short",
                    size=abs(float(pos.get("contracts", 0))),
                    entry_price=float(pos.get("entryPrice", 0)),
                    mark_price=float(pos.get("markPrice", 0)),
                    unrealized_pnl=float(pos.get("unrealizedPnl", 0)),
                    leverage=int(pos.get("leverage", 1)),
                    liquidation_price=float(pos.get("liquidationPrice", 0)),
                    margin_type=pos.get("marginType", "cross"),
                )
                for pos in positions
                if float(pos.get("contracts", 0)) != 0
            ]
        except Exception as e:
            raise ValueError(f"Error fetching positions: {e}") from e

    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """设置杠杆倍数"""
        if self.market_type == MarketType.SPOT:
            raise ValueError("Leverage is only available for futures")

        if not self.api_key:
            raise ValueError("API key required for setting leverage")

        normalized_symbol = self.normalize_symbol(symbol, self.market_type)

        try:
            await self.exchange.set_leverage(leverage, normalized_symbol)
            return True
        except Exception as e:
            raise ValueError(f"Error setting leverage: {e}") from e

    async def fetch_exchange_info(self) -> Dict[str, Any]:
        """获取交易所信息（交易规则、限制等）"""
        try:
            return await self.exchange.fetch_markets()
        except Exception as e:
            raise ValueError(f"Error fetching exchange info: {e}") from e

    def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取交易对信息（精度、限制等）"""
        normalized_symbol = self.normalize_symbol(symbol, self.market_type)
        if self._exchange and self._exchange.markets:
            return self._exchange.markets.get(normalized_symbol)
        return None
