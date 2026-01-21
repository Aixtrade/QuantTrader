"""MACD 策略测试脚本

测试完整数据流：
1. 从币安拉取历史 K 线数据
2. 执行 MACD 策略
3. 输出交易信号（金叉/死叉）
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from quanttrader.data import DataCenterService, MarketDataRequest, MarketType
from quanttrader.strategies import StrategyContext

# 从同目录导入 MACD 策略
from macd_strategy import MACDStrategy, MACDConfig


async def test_macd_strategy():
    """测试 MACD 策略"""

    print("=" * 60)
    print("MACD 策略测试 - 币安数据源")
    print("=" * 60)

    # 初始化策略
    config = MACDConfig(
        fast_period=12,
        slow_period=26,
        signal_period=9,
        require_histogram_confirm=False,  # 简化测试，不需要柱状图确认
    )
    strategy = MACDStrategy(config=config)

    print(f"\n策略配置: {strategy.get_config()}")
    print(f"数据需求: min_bars={strategy.get_data_requirements('1h').min_bars}")

    # 测试现货和永续合约
    test_cases = [
        ("BTC/USDT", "1h", MarketType.SPOT, "现货"),
        ("ETH/USDT", "15m", MarketType.FUTURES, "永续合约"),
    ]

    for symbol, interval, market_type, market_name in test_cases:
        print(f"\n{'─' * 60}")
        print(f"测试: {symbol} {interval} ({market_name})")
        print("─" * 60)

        async with DataCenterService(market_type=market_type) as dc:
            # 拉取足够的历史数据
            request = MarketDataRequest(
                symbol=symbol,
                interval=interval,
                limit=100,  # 获取 100 根 K 线
            )

            data = await dc.get_market_data(request)

            print(f"获取数据: {data['metadata']['count']} 根 K 线")
            print(f"最新收盘价: {data['ohlcv']['close'][-1]:.2f}")

            # 构建策略上下文
            context = StrategyContext(
                symbol=symbol,
                interval=interval,
                current_time=datetime.now(timezone.utc),
                market_data=data["ohlcv"],
                indicators={},
                account_balance=10000.0,
                current_positions={},
            )

            # 执行策略
            result = strategy.execute(context)

            # 输出结果
            print("\n策略执行结果:")
            print(f"  成功: {result.success}")
            print(f"  执行时间: {result.execution_time * 1000:.2f} ms")

            if result.indicators:
                print("\n  MACD 指标:")
                print(f"    MACD Line:  {result.indicators.get('macd', 'N/A'):.4f}")
                print(f"    Signal Line: {result.indicators.get('signal', 'N/A'):.4f}")
                print(f"    Histogram:   {result.indicators.get('histogram', 'N/A'):.4f}")

            for signal in result.signals:
                action_emoji = {"LONG": "📈", "SHORT": "📉", "HOLD": "⏸️"}.get(signal.action, "❓")
                print(f"\n  交易信号: {action_emoji} {signal.action}")
                print(f"    原因: {signal.reason}")
                print(f"    置信度: {signal.confidence:.2%}")

    print(f"\n{'=' * 60}")
    print("测试完成!")
    print("=" * 60)


async def test_macd_signal_detection():
    """测试 MACD 信号检测（模拟多个时间点）"""

    print("\n" + "=" * 60)
    print("MACD 信号检测测试 - 回溯历史数据")
    print("=" * 60)

    strategy = MACDStrategy(
        config=MACDConfig(require_histogram_confirm=False)
    )

    symbol = "BTC/USDT"
    interval = "1h"

    async with DataCenterService(market_type=MarketType.SPOT) as dc:
        # 获取更多历史数据
        data = await dc.get_market_data(
            MarketDataRequest(symbol=symbol, interval=interval, limit=200)
        )

        closes = data["ohlcv"]["close"]
        timestamps = data["ohlcv"]["timestamps"]

        print(f"\n获取 {len(closes)} 根 K 线")
        print(f"时间范围: {datetime.fromtimestamp(timestamps[0]/1000)} ~ {datetime.fromtimestamp(timestamps[-1]/1000)}")

        # 滑动窗口检测信号
        print("\n检测到的交易信号:")
        print("-" * 60)

        signals_found = []
        window_size = 50  # 最小窗口

        for i in range(window_size, len(closes)):
            # 构建子集数据
            window_data = {
                "open": data["ohlcv"]["open"][: i + 1],
                "high": data["ohlcv"]["high"][: i + 1],
                "low": data["ohlcv"]["low"][: i + 1],
                "close": closes[: i + 1],
                "volume": data["ohlcv"]["volume"][: i + 1],
                "timestamps": timestamps[: i + 1],
            }

            context = StrategyContext(
                symbol=symbol,
                interval=interval,
                current_time=datetime.fromtimestamp(timestamps[i] / 1000),
                market_data=window_data,
                indicators={},
                account_balance=10000.0,
                current_positions={},
            )

            result = strategy.execute(context)

            if result.signals:
                signal = result.signals[0]
                if signal.action in ("LONG", "SHORT"):
                    signal_time = datetime.fromtimestamp(timestamps[i] / 1000)
                    signals_found.append({
                        "time": signal_time,
                        "action": signal.action,
                        "price": closes[i],
                        "macd": result.indicators.get("macd"),
                        "signal": result.indicators.get("signal"),
                        "histogram": result.indicators.get("histogram"),
                    })

        if signals_found:
            for s in signals_found[-10:]:  # 显示最近 10 个信号
                emoji = "📈 金叉" if s["action"] == "LONG" else "📉 死叉"
                print(f"{s['time']} | {emoji} | 价格: {s['price']:.2f} | MACD: {s['macd']:.4f}")
        else:
            print("最近无明显金叉/死叉信号")

        print(f"\n共检测到 {len(signals_found)} 个交易信号")


if __name__ == "__main__":
    asyncio.run(test_macd_strategy())
    asyncio.run(test_macd_signal_detection())
