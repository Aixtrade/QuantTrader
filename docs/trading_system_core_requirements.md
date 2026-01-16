# 交易系统核心模块需求规范

> 本文档基于 binatms 项目提炼，作为新项目交易系统开发的参考规范。

---

## 一、概述

### 1.1 系统定位

构建一套模块化、可扩展的量化交易系统，支持：
- 多交易品种（事件合约、U本位永续合约等）
- 多执行模式（回测、模拟盘、实盘）
- 动态策略加载与执行
- 统一的数据获取与缓存

### 1.2 核心闭环流程

```
┌──────────────────────────────────────────────────────────────────────┐
│                        交易系统核心闭环                              │
└──────────────────────────────────────────────────────────────────────┘

  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
  │ 数据Hub │ -> │ 加载策略 │ -> │ 生成信号 │ -> │ 执行交易 │ -> │ 更新账户 │
  └─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘
       │                                                            │
       └────────────────────── 生成报告 <───────────────────────────┘
```

### 1.3 架构分层

```
┌─────────────────────────────────────────────────────────────┐
│                    API / 任务调度层                          │
└──────────────────────────┬──────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         ↓                 ↓                 ↓
   ┌───────────┐    ┌───────────┐    ┌───────────┐
   │ 交易引擎   │    │ 策略系统   │    │ 数据 Hub  │
   │ (Engine)  │    │ (Strategy)│    │ (DataHub) │
   └─────┬─────┘    └───────────┘    └───────────┘
         │
    ┌────┴────┐
    ↓         ↓
┌────────┐ ┌────────┐
│ Trader │ │Account │
│ 交易层  │ │ 账户层 │
└────────┘ └────────┘
```

---

## 二、动态策略系统

### 2.1 策略基类接口

```python
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

class BaseStrategy(ABC):
    """策略基类 - 所有用户策略必须继承此类"""

    def __init__(
        self,
        name: str,
        version: str = "1.0.0",
        description: str = "",
        tags: List[str] = None,
    ):
        self.name = name
        self.version = version
        self.description = description
        self.tags = tags or []

    @abstractmethod
    def execute(self, context: "StrategyContext") -> "StrategyResult":
        """
        策略执行入口 - 必须实现

        Args:
            context: 策略执行上下文，包含市场数据、账户信息等

        Returns:
            StrategyResult: 包含信号、指标、元数据的执行结果
        """
        pass

    def get_config(self) -> Dict[str, Any]:
        """
        获取策略配置参数（可选实现）

        Returns:
            策略配置字典，如 {"threshold": 0.02, "period": 20}
        """
        return {}

    def get_data_requirements(
        self,
        interval: str,
        config: Optional[Dict[str, Any]] = None
    ) -> "StrategyDataRequirements":
        """
        声明策略数据需求（可选实现）

        Args:
            interval: K线数据间隔，如 "1m"
            config: 策略配置

        Returns:
            数据需求配置
        """
        return StrategyDataRequirements()

    def create_signal(
        self,
        action: str,
        symbol: str,
        quantity: float = 0.0,
        **kwargs
    ) -> "StrategySignal":
        """工具方法：创建交易信号"""
        return StrategySignal(
            action=action,
            symbol=symbol,
            quantity=quantity,
            **kwargs
        )
```

### 2.2 复合策略基类

```python
class CompositeStrategy(BaseStrategy):
    """
    复合组合策略 - 可调用多个子策略

    支持两种执行模式和多种信号聚合方式，实现策略组合管理。
    """

    def __init__(
        self,
        name: str,
        sub_strategies: List[str],
        execution_mode: str = "parallel",
        signal_aggregation: str = "vote",
        version: str = "1.0.0",
        description: str = "",
    ):
        """
        初始化复合策略

        Args:
            name: 策略名称
            sub_strategies: 子策略 ID 列表
            execution_mode: 执行模式 (parallel | sequential)
            signal_aggregation: 信号聚合方式 (vote | first | weighted)
        """
        super().__init__(name, version, description)
        self.sub_strategies = sub_strategies
        self.execution_mode = execution_mode
        self.signal_aggregation = signal_aggregation

    def execute(self, context: "StrategyContext") -> "StrategyResult":
        """
        聚合多个子策略的信号

        执行模式:
        - parallel: 所有子策略同时执行，最后聚合信号
        - sequential: 按顺序执行，前一个策略输出可作为后一个输入

        信号聚合方式:
        - vote: 多数投票决定最终信号
        - first: 采用第一个有效信号
        - weighted: 按置信度加权聚合
        """
        pass

    def _aggregate_signals_vote(
        self,
        all_signals: List[List["StrategySignal"]]
    ) -> List["StrategySignal"]:
        """多数投票聚合信号"""
        pass

    def _aggregate_signals_weighted(
        self,
        all_signals: List[List["StrategySignal"]]
    ) -> List["StrategySignal"]:
        """置信度加权聚合信号"""
        pass
```

#### 执行模式对比

| 模式 | 特点 | 适用场景 |
|------|------|----------|
| parallel | 子策略独立执行，结果聚合 | 多因子策略、信号确认 |
| sequential | 链式执行，可传递状态 | 过滤器模式、多阶段决策 |

### 2.3 数据模型定义

#### 2.3.1 策略执行上下文

```python
@dataclass
class StrategyContext:
    """策略执行上下文"""

    symbol: str                              # 交易对，如 "BTCUSDT"
    interval: str                            # K线数据间隔，如 "1m"
    current_time: datetime                   # 当前执行时间
    market_data: Dict[str, List[float]]      # 市场数据 (OHLCV)
    indicators: Dict[str, Any] = None        # 预计算的技术指标 (TA-Lib)
    account_balance: float = 10000.0         # 账户余额
    current_positions: Dict[str, float] = None  # 当前持仓 {symbol: quantity}

# market_data 标准结构
market_data = {
    "open": [float, ...],         # 开盘价序列
    "high": [float, ...],         # 最高价序列
    "low": [float, ...],          # 最低价序列
    "close": [float, ...],        # 收盘价序列
    "volume": [float, ...],       # 成交量序列
    "timestamps": [str, ...],     # 时间戳序列
    # 可选字段
    "quote_volume": [float, ...], # 报价资产成交量
    "trade_count": [float, ...],  # 交易笔数
}
```

#### 2.3.2 策略执行结果

```python
@dataclass
class StrategyResult:
    """策略执行结果"""

    signals: List["StrategySignal"]    # 交易信号列表
    indicators: Dict[str, Any]         # 技术指标字典
    metadata: Dict[str, Any]           # 元数据信息
    execution_time: float              # 执行时间（秒）
    success: bool                      # 执行是否成功
    error_message: Optional[str] = None  # 错误信息
```

#### 2.3.3 策略信号

```python
@dataclass
class StrategySignal:
    """策略信号"""

    action: str                          # 动作类型（见下表）
    symbol: str                          # 交易对
    quantity: float = 0.0                # 交易量
    price: Optional[float] = None        # 执行价格
    stop_loss: Optional[float] = None    # 止损价
    take_profit: Optional[float] = None  # 止盈价
    confidence: float = 1.0              # 信号置信度 [0, 1]
    reason: str = ""                     # 信号原因

# 支持的 action 类型
# 通用：BUY, SELL, HOLD
# 永续合约：LONG, SHORT, CLOSE_LONG, CLOSE_SHORT, CLOSE
```

#### 2.3.4 数据需求配置

```python
@dataclass
class StrategyDataRequirements:
    """策略数据需求配置"""

    use_time_range: bool = True                   # 是否按时间范围拉取
    min_bars: int = 0                             # 最少K线数量
    prefer_closed_bar: bool = False               # 是否只使用已收盘K线
    extra_seconds: int = 0                        # 额外冗余秒数
    warmup_periods: int = 50                      # interval级预热条数
    max_timeframe_required: Optional[str] = None  # 最大时间周期（多周期策略必须声明）
```

### 2.4 信号处理规则

当策略产生多个信号时，引擎按以下规则处理：

#### 信号冲突处理

| 场景 | 处理规则 |
|------|----------|
| 同方向多信号 | 取置信度最高的信号 |
| 相反方向信号 | 高置信度优先；相同置信度则取消 |
| 信号置信度 < 阈值 | 忽略该信号（默认阈值 0.5） |
| HOLD 与其他信号 | 忽略 HOLD，执行其他信号 |

#### 信号优先级

```python
SIGNAL_PRIORITY = {
    # 平仓信号优先级最高
    "CLOSE": 100,
    "CLOSE_LONG": 90,
    "CLOSE_SHORT": 90,
    # 开仓信号
    "LONG": 50,
    "SHORT": 50,
    "BUY": 50,
    "SELL": 50,
    # 持有信号优先级最低
    "HOLD": 0,
}
```

#### 置信度阈值配置

```python
@dataclass
class SignalFilterConfig:
    """信号过滤配置"""

    min_confidence: float = 0.5        # 最小置信度阈值
    enable_conflict_resolution: bool = True  # 启用冲突处理
    prefer_close_signals: bool = True  # 优先处理平仓信号
```

### 2.5 策略加载机制

```python
class StrategyLoader:
    """策略加载器 - 动态加载 Python 策略文件"""

    def __init__(self, strategies_dir: str):
        self.strategies_dir = Path(strategies_dir)
        self.loaded_strategies: Dict[str, LoadedStrategyEntry] = {}

    def load_all_strategies(self) -> Dict[str, LoadedStrategyEntry]:
        """扫描目录，加载所有 .py 策略文件"""
        pass

    def load_strategy_from_file(self, file_path: str) -> Optional[BaseStrategy]:
        """
        从 Python 文件动态导入策略

        实现要点：
        1. 使用 importlib.util 动态导入模块
        2. 查找继承 BaseStrategy 的类或 strategy_instance 变量
        3. 实例化策略获取元数据
        4. 保存工厂函数以便后续创建新实例
        """
        pass

    def execute_strategy(
        self,
        strategy_id: str,
        context: StrategyContext
    ) -> Optional[StrategyResult]:
        """创建新策略实例并执行"""
        pass

    def reload_strategy_from_file(self, file_path: str) -> bool:
        """热重载策略（删除缓存，重新导入）"""
        pass

@dataclass
class LoadedStrategyEntry:
    """策略加载记录"""

    factory: Callable[[], BaseStrategy]  # 工厂函数
    module_name: str                     # 模块名称
    file_path: str                       # 文件路径
    metadata: Dict[str, Any]             # 元数据
```

---

## 三、交易类型

### 3.1 事件合约 (Events)

#### 3.1.1 特性

| 特性 | 说明 |
|------|------|
| 投入方式 | 固定金额 |
| 结果类型 | 二元（盈/亏） |
| 支持动作 | BUY / SELL |
| 赔付方式 | 固定倍数 |

#### 3.1.2 交易逻辑

```python
class EventsTrader(BaseTrader):
    """事件合约交易器"""

    DEFAULT_PAYOUT_MULTIPLIER = 1.8  # 默认赔付倍数

    async def execute_trade(
        self,
        signal: StrategySignal,
        price: float,
        account: BaseAccount,
        config: EventsBacktestConfig,
    ) -> Tuple[TradeResult, EventsTradeRecord]:
        """
        执行事件合约交易

        核心逻辑：
        1. 固定投入金额（从 signal.quantity 或 config 获取）
        2. 记录开仓价格和时间
        3. 等待到期时间（K线收盘）
        4. 比较开仓价和收盘价判断胜负
        5. 胜利：返还投入 × 赔付倍数
        6. 失败：扣除全部投入

        赔付倍数格式：
        - >= 1：总赔付倍数（如1.8表示返还1.8倍投入）
        - 0 < x < 1：净收益率（如0.8表示盈利80%）
        """
        pass
```

#### 3.1.3 配置参数

```python
@dataclass
class EventsBacktestConfig:
    """事件合约回测配置"""

    symbol: str                    # 交易对
    interval: str                  # K线周期
    investment_amount: float       # 单次投入金额
    payout_multiplier: float = 1.8 # 赔付倍数
    start_time: Optional[int] = None
    end_time: Optional[int] = None
```

### 3.2 U本位永续合约 (Futures)

#### 3.2.1 特性

| 特性 | 说明 |
|------|------|
| 持仓模式 | 双向持仓（可同时持多/空） |
| 杠杆 | 1-125x 可配置 |
| 保证金 | 分方向独立管理 |
| 止盈止损 | 基于标记价格触发 |
| 强平机制 | 基于标记价格 + 维持保证金率 |
| 资金费率 | 按固定间隔结算（如每8小时） |

#### 3.2.2 信号动作映射

| 信号 | 解析结果 | 说明 |
|------|----------|------|
| `LONG` / `BUY` / `OPEN_LONG` | (OPEN, LONG) | 开多仓 |
| `SHORT` / `SELL` / `OPEN_SHORT` | (OPEN, SHORT) | 开空仓 |
| `CLOSE_LONG` | (CLOSE, LONG) | 平多仓 |
| `CLOSE_SHORT` | (CLOSE, SHORT) | 平空仓 |
| `CLOSE` | (CLOSE_ALL, None) | 平所有仓位 |
| `HOLD` | (HOLD, None) | 不操作 |

#### 3.2.3 价格使用原则

| 场景 | 使用价格 |
|------|----------|
| 开仓/平仓成交 | 最新成交价（lastPrice）+ 滑点 |
| 盈亏计算 | 标记价格（markPrice） |
| 强平检查 | 标记价格（markPrice） |
| 止盈止损触发 | 标记价格（markPrice） |

#### 3.2.4 交易逻辑

```python
class FuturesTrader(BaseTrader):
    """永续合约交易器 - 双向持仓模式"""

    async def execute_trade(
        self,
        signal: StrategySignal,
        price: float,
        account: FuturesSimulatedAccount,
        config: FuturesBacktestConfig,
        position_manager: HedgePositionManager,
    ) -> Tuple[TradeResult, List[FuturesTrade]]:
        """执行永续合约交易"""
        pass

    def _open_position(
        self,
        signal: StrategySignal,
        price: float,
        side: PositionSide,
        account: FuturesSimulatedAccount,
        config: FuturesBacktestConfig,
    ) -> Tuple[TradeResult, FuturesPosition, FuturesTrade]:
        """
        开仓逻辑

        计算公式：
        1. 保证金 = 账户余额 × 仓位比例
        2. 名义仓位 = 保证金 × 杠杆
        3. 开仓手续费 = 名义仓位 × taker_fee
        4. 滑点后价格 = price × (1 ± slippage)
        5. 仓位数量 = 名义仓位 / 开仓价格
        6. 强平价格 = entry_price × (1 ± maintenance_ratio ∓ 1/leverage)
        """
        pass

    def _close_position(
        self,
        position: FuturesPosition,
        price: float,
        account: FuturesSimulatedAccount,
        config: FuturesBacktestConfig,
        reason: str,
    ) -> Tuple[TradeResult, FuturesTrade]:
        """
        平仓逻辑

        盈亏计算：
        - 多仓: realized_pnl = (exit_price - entry_price) × size
        - 空仓: realized_pnl = (entry_price - exit_price) × size
        - 平仓手续费 = exit_price × size × taker_fee
        - 净盈亏 = realized_pnl - exit_fee - entry_fee
        """
        pass

    def check_and_execute_stop_orders(
        self,
        position: FuturesPosition,
        mark_price: float,
        account: FuturesSimulatedAccount,
        config: FuturesBacktestConfig,
    ) -> Optional[Tuple[TradeResult, FuturesTrade]]:
        """
        检查止盈止损（按优先级）

        优先级：
        1. 强平（liquidation）
        2. 止损（stop_loss）
        3. 止盈（take_profit）
        4. 追踪止损（trailing_stop）
        """
        pass
```

#### 3.2.5 配置参数

```python
@dataclass
class FuturesBacktestConfig:
    """永续合约回测配置"""

    symbol: str
    interval: str                         # K线数据间隔
    leverage: int = 10                    # 杠杆倍数
    position_size_pct: float = 0.1        # 仓位比例（相对账户余额）
    taker_fee: float = 0.0004             # taker 手续费率
    maker_fee: float = 0.0002             # maker 手续费率
    slippage: float = 0.0005              # 滑点
    maintenance_margin_ratio: float = 0.004  # 维持保证金率
    funding_rate_interval: int = 28800    # 资金费率结算间隔（秒）
    start_time: Optional[int] = None
    end_time: Optional[int] = None
```

#### 3.2.6 持仓管理

```python
@dataclass
class FuturesPosition:
    """永续合约持仓"""

    symbol: str
    side: PositionSide              # LONG / SHORT
    entry_price: float
    size: float                     # 持仓数量
    leverage: int
    margin: float                   # 占用保证金
    entry_time: datetime
    entry_fee: float = 0.0          # 开仓手续费

    # 实时更新字段
    unrealized_pnl: float = 0.0     # 未实现盈亏
    liquidation_price: float = 0.0  # 强平价格

    # 止盈止损
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    trailing_stop_price: Optional[float] = None
    highest_price: float = 0.0      # 追踪止损用
    lowest_price: float = float('inf')


class HedgePositionManager:
    """双向持仓管理器"""

    symbol: str
    long_position: Optional[FuturesPosition] = None
    short_position: Optional[FuturesPosition] = None

    def get_position(self, side: PositionSide) -> Optional[FuturesPosition]:
        """获取指定方向持仓"""
        pass

    def set_position(self, position: Optional[FuturesPosition], side: PositionSide):
        """设置指定方向持仓"""
        pass

    def has_position(self, side: Optional[PositionSide] = None) -> bool:
        """检查是否有持仓"""
        pass

    def get_total_margin(self) -> float:
        """获取总占用保证金"""
        pass
```

---

## 四、账户管理

### 4.1 账户体系

```
BaseAccount (抽象基类)
├── SimulatedAccount (简单模拟账户)
│   └── VirtualAccount (虚拟账户 - Paper 模式)
├── FuturesSimulatedAccount (永续合约模拟账户)
└── RealAccount (真实账户 - Live 模式)
```

### 4.2 账户基类

```python
class BaseAccount(ABC):
    """账户基类"""

    def __init__(self, initial_capital: float):
        self._balance = float(initial_capital)

    @property
    def balance(self) -> float:
        """可用余额"""
        return self._balance

    @abstractmethod
    def apply_trade_result(self, trade_result: TradeResult) -> TradeResult:
        """根据交易结果更新资金"""
        pass
```

### 4.3 简单模拟账户

```python
class SimulatedAccount(BaseAccount):
    """简单模拟账户 - 用于事件合约回测"""

    def apply_trade_result(self, trade_result: TradeResult) -> TradeResult:
        """
        更新余额

        逻辑：balance += trade_result.pnl
        """
        self._balance += trade_result.pnl
        trade_result.balance_after = self._balance
        return trade_result
```

### 4.4 永续合约模拟账户

```python
class FuturesSimulatedAccount(BaseAccount):
    """永续合约模拟账户 - 支持双向持仓"""

    def __init__(self, initial_capital: float):
        super().__init__(initial_capital)
        self._long_margin_locked = 0.0   # 多仓占用保证金
        self._short_margin_locked = 0.0  # 空仓占用保证金

    @property
    def margin_locked(self) -> float:
        """总占用保证金"""
        return self._long_margin_locked + self._short_margin_locked

    @property
    def wallet_balance(self) -> float:
        """钱包余额（含保证金，不含未实现盈亏）"""
        return self._balance + self.margin_locked

    def lock_margin(self, amount: float, side: PositionSide):
        """
        锁定保证金（开仓时调用）

        流程：
        1. 检查余额是否足够
        2. 扣除余额
        3. 增加对应方向的锁定保证金
        """
        if amount > self._balance:
            raise InsufficientFundsError(...)
        self._balance -= amount
        if side == PositionSide.LONG:
            self._long_margin_locked += amount
        else:
            self._short_margin_locked += amount

    def release_margin(self, amount: float, side: PositionSide):
        """
        释放保证金（平仓时调用）

        流程：
        1. 减少对应方向的锁定保证金
        2. 增加余额
        """
        if side == PositionSide.LONG:
            self._long_margin_locked -= amount
        else:
            self._short_margin_locked -= amount
        self._balance += amount

    def apply_fee(self, fee: float):
        """扣除手续费"""
        self._balance -= fee

    def apply_pnl(self, pnl: float):
        """应用已实现盈亏"""
        self._balance += pnl
```

### 4.5 虚拟账户

```python
class VirtualAccount(SimulatedAccount):
    """虚拟账户 - Paper 模式"""

    def __init__(self, initial_capital: float, account_id: str = None):
        super().__init__(initial_capital)
        self.account_id = account_id or str(uuid.uuid4())
        self.trade_history: List[TradeResult] = []

    def apply_trade_result(self, trade_result: TradeResult) -> TradeResult:
        """更新余额并记录交易历史"""
        result = super().apply_trade_result(trade_result)
        self.trade_history.append(result)
        return result
```

### 4.6 真实账户

```python
class RealAccount(BaseAccount):
    """真实账户 - Live 模式（接口定义）"""

    def __init__(self, api_client: ExchangeAPIClient):
        self.api_client = api_client

    @property
    def balance(self) -> float:
        """从交易所 API 获取实时余额"""
        return self.api_client.get_balance()

    def apply_trade_result(self, trade_result: TradeResult) -> TradeResult:
        """真实交易已通过 API 执行，仅记录结果"""
        return trade_result
```

---

## 五、交易引擎

### 5.1 引擎架构

```
BaseEngine (抽象基类)
├── BacktestEngine
│   ├── EventsBacktestEngine (事件合约回测)
│   └── FuturesBacktestEngine (永续合约回测)
└── RealtimeEngine (实时引擎)
    ├── Paper 模式
    └── Live 模式
```

### 5.2 引擎基类

```python
class BaseEngine(ABC):
    """执行引擎基类"""

    def __init__(self, mode: ExecutionMode):
        self.mode = mode  # BACKTEST / PAPER / LIVE

    @abstractmethod
    async def run(
        self,
        strategy: BaseStrategy,
        config: ExecutionConfig,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> AsyncGenerator[ExecutionEvent, None]:
        """
        启动策略执行，流式返回事件

        使用异步生成器模式，支持：
        - 实时进度推送
        - 中途暂停/恢复
        - 流式结果返回
        """
        yield ExecutionEvent(...)


class ExecutionMode(str, Enum):
    """执行模式"""
    BACKTEST = "backtest"  # 历史回测
    PAPER = "paper"        # 模拟盘
    LIVE = "live"          # 实盘


@dataclass
class ExecutionEvent:
    """执行事件"""

    event_type: str        # tick, trade, progress, complete, error
    data: Dict[str, Any]
    timestamp: datetime
```

### 5.3 回测引擎

```python
class BacktestEngine(BaseEngine):
    """回测引擎基类"""

    def __init__(self):
        super().__init__(ExecutionMode.BACKTEST)
        self.data_service = DataCenterService()

    async def run(
        self,
        strategy: BaseStrategy,
        config: BacktestConfig,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> AsyncGenerator[ExecutionEvent, None]:
        """
        Playback 流式回测

        执行流程：
        1. 加载预热数据（考虑策略声明的 max_timeframe_required）
        2. 初始化账户和持仓管理器
        3. 创建流式数据加载器
        4. 逐点执行：
           a. 获取当前时间点的市场数据
           b. 更新持仓盈亏（使用标记价格）
           c. 检查止盈止损
           d. 构建策略上下文
           e. 调用 strategy.execute()
           f. 解析信号，执行交易
           g. 推送进度事件
        5. 生成汇总报告
        """
        pass


class StreamingDataLoader:
    """流式数据加载器"""

    def __init__(
        self,
        symbol: str,
        interval: str,
        start_time: int,
        end_time: int,
        batch_size: int = 200,
    ):
        self.batch_size = batch_size
        self.preload_enabled = True  # 后台预加载下一批次

    async def __aiter__(self):
        """异步迭代器，按批次加载数据"""
        pass
```

#### 5.3.1 Playback 特性

| 特性 | 说明 |
|------|------|
| 流式加载 | 按批次加载数据，避免一次性加载全部 |
| 逐点推送 | 每个时间点通过 WebSocket 实时推送 |
| 可控播放 | 支持变速（0-999x）、暂停、恢复 |
| 批量优化 | 高速模式下批量推送减少网络开销 |

#### 5.3.2 批量推送策略

```python
BATCH_PUSH_THRESHOLDS = {
    (0, 10): 1,        # 0-10x: 每个tick都推送
    (10, 50): 5,       # 10-50x: 每5个tick推送一次
    (50, 100): 10,     # 50-100x: 每10个tick推送一次
    (100, 999): 20,    # 100x+: 每20个tick推送一次
}
MAX_MODE_BATCH_SIZE = 200  # 极速模式批量推送
```

### 5.4 实时引擎

```python
class RealtimeEngine(BaseEngine):
    """实时引擎 - Paper / Live 模式"""

    def __init__(self, mode: ExecutionMode):
        super().__init__(mode)
        self.ws_manager = WebSocketDataManager()

    async def run(
        self,
        strategy: BaseStrategy,
        config: RealtimeConfig,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> AsyncGenerator[ExecutionEvent, None]:
        """
        实时策略执行

        执行流程：
        1. 获取初始市场数据
        2. 订阅 WebSocket 数据流
        3. 事件驱动循环：
           a. 接收 K线更新事件
           b. 更新市场数据
           c. 调用 strategy.execute()
           d. 处理交易信号
           e. Paper: 模拟执行
           f. Live: 调用交易所 API
        4. 推送信号和状态事件
        """
        pass
```

### 5.5 回测报告模型

```python
@dataclass
class EquityPoint:
    """权益曲线点"""
    timestamp: datetime
    equity: float              # 当前权益
    drawdown: float            # 当前回撤金额
    drawdown_pct: float        # 当前回撤百分比


@dataclass
class TradeRecord:
    """交易记录"""
    trade_id: str
    symbol: str
    action: str                # BUY/SELL/LONG/SHORT/CLOSE...
    entry_time: datetime
    entry_price: float
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    quantity: float = 0.0
    pnl: float = 0.0           # 盈亏金额
    pnl_pct: float = 0.0       # 盈亏百分比
    fees: float = 0.0          # 手续费
    holding_period: Optional[timedelta] = None  # 持仓时间


@dataclass
class BacktestReport:
    """回测报告"""

    # ===== 基础信息 =====
    strategy_name: str
    symbol: str
    interval: str
    start_time: datetime
    end_time: datetime
    duration_days: int
    initial_capital: float
    final_capital: float

    # ===== 收益指标 =====
    total_return: float        # 总收益率
    annual_return: float       # 年化收益率
    total_pnl: float           # 总盈亏金额

    # ===== 交易统计 =====
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float            # 胜率
    avg_win: float             # 平均盈利
    avg_loss: float            # 平均亏损
    profit_factor: float       # 盈亏比
    avg_holding_period: timedelta  # 平均持仓时间

    # ===== 风险指标 =====
    max_drawdown: float        # 最大回撤金额
    max_drawdown_pct: float    # 最大回撤百分比
    max_drawdown_duration: timedelta  # 最大回撤持续时间
    sharpe_ratio: float        # 夏普比率
    sortino_ratio: float       # 索提诺比率
    calmar_ratio: float        # 卡尔玛比率

    # ===== 详细数据 =====
    equity_curve: List[EquityPoint]
    trade_records: List[TradeRecord]
    monthly_returns: Dict[str, float]  # {"2024-01": 0.05, "2024-02": -0.02}
    daily_returns: List[float]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "summary": {
                "strategy_name": self.strategy_name,
                "symbol": self.symbol,
                "interval": self.interval,
                "period": f"{self.start_time} - {self.end_time}",
                "duration_days": self.duration_days,
                "initial_capital": self.initial_capital,
                "final_capital": self.final_capital,
            },
            "returns": {
                "total_return": f"{self.total_return:.2%}",
                "annual_return": f"{self.annual_return:.2%}",
                "total_pnl": self.total_pnl,
            },
            "trades": {
                "total": self.total_trades,
                "winning": self.winning_trades,
                "losing": self.losing_trades,
                "win_rate": f"{self.win_rate:.2%}",
                "profit_factor": f"{self.profit_factor:.2f}",
            },
            "risk": {
                "max_drawdown": f"{self.max_drawdown_pct:.2%}",
                "sharpe_ratio": f"{self.sharpe_ratio:.2f}",
                "sortino_ratio": f"{self.sortino_ratio:.2f}",
                "calmar_ratio": f"{self.calmar_ratio:.2f}",
            },
        }


class ReportGenerator:
    """回测报告生成器"""

    @staticmethod
    def generate(
        trade_records: List[TradeRecord],
        equity_curve: List[EquityPoint],
        config: BacktestConfig,
        initial_capital: float,
        final_capital: float,
    ) -> BacktestReport:
        """
        根据交易记录和权益曲线生成完整报告

        计算公式:
        - 夏普比率 = (年化收益 - 无风险利率) / 年化波动率
        - 索提诺比率 = (年化收益 - 无风险利率) / 下行波动率
        - 卡尔玛比率 = 年化收益 / 最大回撤
        - 盈亏比 = 总盈利 / 总亏损
        """
        pass
```

---

## 六、数据 Hub

### 6.1 数据中心架构

```
DataCenterService (统一入口)
├── KlineDataService (K线数据)
│   ├── 现货 K线
│   ├── U本位永续 K线
│   └── 币本位永续 K线
├── MarkPriceKlineService (标记价格 K线)
├── IndexPriceKlineService (指数价格 K线)
├── IndicatorDataService (技术指标)
│   ├── MACD
│   ├── EMA
│   └── BOLL
└── DataCenterCache (缓存层)
```

### 6.2 数据中心服务

```python
class DataCenterService:
    """数据中心服务 - 统一数据获取入口"""

    def __init__(self, base_url: str = None, enable_cache: bool = True):
        self.kline_service = KlineDataService(base_url)
        self.indicator_service = IndicatorDataService(base_url)
        self.mark_price_service = MarkPriceKlineService(base_url)
        self.index_price_service = IndexPriceKlineService(base_url)
        self.cache = DataCenterCache() if enable_cache else None

    async def get_market_data(
        self,
        request: MarketDataRequest
    ) -> Dict[str, Any]:
        """
        获取市场数据（带缓存）

        返回格式：
        {
            "ohlcv": {
                "open": [...], "high": [...], "low": [...],
                "close": [...], "volume": [...], "timestamps": [...]
            },
            "metadata": {
                "symbol": "...",
                "interval": "...",
                "count": 100
            }
        }
        """
        pass

    async def get_historical_klines_batch(
        self,
        request: MarketDataRequest,
        max_requests: int = 100,
    ) -> Dict[str, Any]:
        """批量获取历史 K线数据"""
        pass

    async def get_macd(self, request: MACDRequest) -> Dict[str, Any]:
        """获取 MACD 指标"""
        pass

    async def get_ema(self, request: EMARequest) -> Dict[str, Any]:
        """获取 EMA 指标"""
        pass

    async def get_boll(self, request: BOLLRequest) -> Dict[str, Any]:
        """获取布林带指标"""
        pass
```

### 6.3 数据请求模型

```python
@dataclass
class MarketDataRequest:
    """市场数据请求"""

    symbol: str                       # 交易对
    interval: str                     # K线周期 (1m, 5m, 15m, 1h, 4h, 1d)
    exchange: str = "binance"         # 交易所
    limit: int = 100                  # 数据条数 (1-1000)
    start_time: Optional[int] = None  # 开始时间（毫秒）
    end_time: Optional[int] = None    # 结束时间（毫秒）
```

### 6.4 K线数据服务

```python
class KlineDataService(DataCenterServiceBase):
    """K线数据服务"""

    async def get_kline_data(
        self,
        request: MarketDataRequest
    ) -> Dict[str, Any]:
        """
        获取 K线数据

        返回 Binance 格式：
        [
            [open_time, open, high, low, close, volume,
             close_time, quote_volume, trade_count,
             taker_buy_volume, taker_buy_quote_volume]
        ]
        """
        pass

    def extract_ohlcv_data(
        self,
        klines: List[List]
    ) -> Dict[str, List[float]]:
        """提取 OHLCV 数据"""
        pass

    def validate_market_data_request(
        self,
        request: MarketDataRequest
    ) -> bool:
        """验证请求参数"""
        pass
```

### 6.5 缓存机制

```python
class DataCenterCache:
    """数据中心缓存"""

    def __init__(self, cache_ttl: int = 300):
        self.cache: Dict[str, Tuple[Any, float]] = {}
        self.cache_ttl = cache_ttl  # 秒

    def get_kline(self, request: MarketDataRequest) -> Optional[Dict]:
        """
        获取缓存的 K线数据

        缓存键格式：kline_{symbol}_{interval}_{limit}
        """
        cache_key = self._generate_kline_cache_key(request)
        if cache_key in self.cache:
            data, timestamp = self.cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                return data
            del self.cache[cache_key]  # 过期删除
        return None

    def set_kline(self, request: MarketDataRequest, data: Dict):
        """设置 K线缓存"""
        cache_key = self._generate_kline_cache_key(request)
        self.cache[cache_key] = (data, time.time())

    def clear_expired(self):
        """清除所有过期缓存"""
        pass
```

### 6.6 容错机制

#### 6.6.1 服务基类

```python
class DataCenterServiceBase:
    """数据服务基类 - 提供熔断器和重试"""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            timeout=30
        )
        self.client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """异步上下文管理器 - 创建 HTTP 客户端"""
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5, read=30, write=5, pool=60),
            limits=httpx.Limits(max_connections=100)
        )
        return self

    async def __aexit__(self, *args):
        """关闭 HTTP 客户端"""
        if self.client:
            await self.client.aclose()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1.0, max=4.0),
        retry=retry_if_exception_type((NetworkException, httpx.TimeoutException))
    )
    async def _make_request(self, url: str, params: dict = None) -> dict:
        """发送 HTTP 请求（带熔断和重试）"""
        if not self.circuit_breaker.allow_request():
            raise CircuitBreakerOpenError(...)

        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            self.circuit_breaker.record_success()
            return response.json()
        except Exception as e:
            self.circuit_breaker.record_failure()
            raise
```

#### 6.6.2 熔断器

```python
class CircuitBreaker:
    """熔断器"""

    def __init__(self, failure_threshold: int = 5, timeout: int = 30):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = CircuitState.CLOSED

    def allow_request(self) -> bool:
        """
        检查是否允许请求

        状态转换：
        CLOSED (正常)
            → 失败次数 >= threshold → OPEN (熔断)
        OPEN (熔断)
            → 等待 timeout 秒 → HALF_OPEN (试探)
        HALF_OPEN (试探)
            → 成功 → CLOSED
            → 失败 → OPEN
        """
        pass

    def record_success(self):
        """记录成功"""
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def record_failure(self):
        """记录失败"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
```

### 6.7 时区同步

确保本地时间与交易所时间精准同步，避免因时区差异导致数据错位。

```python
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


class TimeZoneManager:
    """时区管理器 - 确保本地时间与交易所时间精准同步"""

    def __init__(self, local_tz: str = "Asia/Shanghai"):
        """
        初始化时区管理器

        Args:
            local_tz: 本地时区，默认 "Asia/Shanghai"
        """
        self.local_tz = ZoneInfo(local_tz)
        self.exchange_tz = timezone.utc  # 交易所统一使用 UTC

    def to_exchange_time(self, local_time: datetime) -> datetime:
        """
        本地时间 → 交易所时间 (UTC)

        Args:
            local_time: 本地时间（可带或不带时区信息）

        Returns:
            UTC 时间
        """
        if local_time.tzinfo is None:
            local_time = local_time.replace(tzinfo=self.local_tz)
        return local_time.astimezone(self.exchange_tz)

    def to_local_time(self, exchange_time: datetime) -> datetime:
        """
        交易所时间 (UTC) → 本地时间

        Args:
            exchange_time: UTC 时间

        Returns:
            本地时间
        """
        return exchange_time.astimezone(self.local_tz)

    def get_current_exchange_time(self) -> datetime:
        """获取当前交易所时间 (UTC)"""
        return datetime.now(self.exchange_tz)

    def to_timestamp_ms(self, dt: datetime) -> int:
        """将 datetime 转换为毫秒时间戳"""
        return int(dt.timestamp() * 1000)

    def from_timestamp_ms(self, ts_ms: int) -> datetime:
        """将毫秒时间戳转换为 UTC datetime"""
        return datetime.fromtimestamp(ts_ms / 1000, tz=self.exchange_tz)

    def align_to_interval(self, ts: datetime, interval: str) -> datetime:
        """
        将时间对齐到 K 线边界

        Args:
            ts: 待对齐的时间
            interval: K线周期，如 "1m", "5m", "1h"

        Returns:
            对齐后的时间
        """
        interval_seconds = self._parse_interval_to_seconds(interval)
        ts_utc = ts.astimezone(self.exchange_tz)
        aligned_ts = (int(ts_utc.timestamp()) // interval_seconds) * interval_seconds
        return datetime.fromtimestamp(aligned_ts, tz=self.exchange_tz)

    @staticmethod
    def _parse_interval_to_seconds(interval: str) -> int:
        """解析时间间隔为秒数"""
        unit = interval[-1]
        value = int(interval[:-1])
        multipliers = {"m": 60, "h": 3600, "d": 86400, "w": 604800}
        return value * multipliers.get(unit, 60)
```

#### 时区使用原则

| 场景 | 使用时区 |
|------|----------|
| API 请求参数 | UTC 毫秒时间戳 |
| 数据存储 | UTC 时间 |
| 日志记录 | 本地时间（便于阅读） |
| 用户展示 | 本地时间 |

### 6.8 技术指标计算服务

基于 TA-Lib 的技术指标计算服务，在引擎层预计算后通过 `StrategyContext.indicators` 传入策略。

```python
import numpy as np
import talib


class TALibIndicatorService:
    """
    基于 TA-Lib 的技术指标计算服务

    在引擎层预计算，通过 StrategyContext.indicators 传入策略
    """

    @staticmethod
    def calculate_macd(
        close: np.ndarray,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ) -> Dict[str, np.ndarray]:
        """
        计算 MACD 指标

        Returns:
            {"macd": array, "signal": array, "histogram": array}
        """
        macd, signal, hist = talib.MACD(
            close,
            fastperiod=fast_period,
            slowperiod=slow_period,
            signalperiod=signal_period
        )
        return {"macd": macd, "signal": signal, "histogram": hist}

    @staticmethod
    def calculate_ema(close: np.ndarray, period: int) -> np.ndarray:
        """计算 EMA 指数移动平均"""
        return talib.EMA(close, timeperiod=period)

    @staticmethod
    def calculate_sma(close: np.ndarray, period: int) -> np.ndarray:
        """计算 SMA 简单移动平均"""
        return talib.SMA(close, timeperiod=period)

    @staticmethod
    def calculate_bollinger(
        close: np.ndarray,
        period: int = 20,
        std_dev: float = 2.0
    ) -> Dict[str, np.ndarray]:
        """
        计算布林带

        Returns:
            {"upper": array, "middle": array, "lower": array}
        """
        upper, middle, lower = talib.BBANDS(
            close,
            timeperiod=period,
            nbdevup=std_dev,
            nbdevdn=std_dev
        )
        return {"upper": upper, "middle": middle, "lower": lower}

    @staticmethod
    def calculate_rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
        """计算 RSI 相对强弱指标"""
        return talib.RSI(close, timeperiod=period)

    @staticmethod
    def calculate_atr(
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        period: int = 14
    ) -> np.ndarray:
        """计算 ATR 平均真实波幅"""
        return talib.ATR(high, low, close, timeperiod=period)

    @staticmethod
    def calculate_stochastic(
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        fastk_period: int = 14,
        slowk_period: int = 3,
        slowd_period: int = 3
    ) -> Dict[str, np.ndarray]:
        """
        计算 KDJ/Stochastic 指标

        Returns:
            {"slowk": array, "slowd": array}
        """
        slowk, slowd = talib.STOCH(
            high, low, close,
            fastk_period=fastk_period,
            slowk_period=slowk_period,
            slowd_period=slowd_period
        )
        return {"slowk": slowk, "slowd": slowd}

    @staticmethod
    def calculate_adx(
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        period: int = 14
    ) -> np.ndarray:
        """计算 ADX 平均趋向指标"""
        return talib.ADX(high, low, close, timeperiod=period)
```

#### 引擎中的使用示例

```python
class BacktestEngine:
    """回测引擎 - 预计算技术指标"""

    def _build_context(self, market_data: Dict) -> StrategyContext:
        """构建策略上下文，预计算技术指标"""
        close = np.array(market_data["close"])
        high = np.array(market_data["high"])
        low = np.array(market_data["low"])

        # 预计算常用指标
        indicators = {
            "ema_20": TALibIndicatorService.calculate_ema(close, 20),
            "ema_50": TALibIndicatorService.calculate_ema(close, 50),
            "sma_20": TALibIndicatorService.calculate_sma(close, 20),
            "macd": TALibIndicatorService.calculate_macd(close),
            "rsi_14": TALibIndicatorService.calculate_rsi(close, 14),
            "bollinger": TALibIndicatorService.calculate_bollinger(close),
            "atr_14": TALibIndicatorService.calculate_atr(high, low, close, 14),
            "stochastic": TALibIndicatorService.calculate_stochastic(high, low, close),
            "adx_14": TALibIndicatorService.calculate_adx(high, low, close, 14),
        }

        return StrategyContext(
            symbol=self.config.symbol,
            interval=self.config.interval,
            current_time=current_time,
            market_data=market_data,
            indicators=indicators,
            account_balance=self.account.balance,
            current_positions=self._get_current_positions(),
        )
```

#### 策略中使用指标

```python
class MyStrategy(BaseStrategy):
    def execute(self, context: StrategyContext) -> StrategyResult:
        # 直接使用预计算的指标
        macd = context.indicators["macd"]
        rsi = context.indicators["rsi_14"]

        # 获取最新值
        macd_current = macd["macd"][-1]
        signal_current = macd["signal"][-1]
        rsi_current = rsi[-1]

        # 策略逻辑
        if macd_current > signal_current and rsi_current < 70:
            return self.create_signal("BUY", context.symbol, confidence=0.8)

        return self.create_signal("HOLD", context.symbol)
```

---

## 七、风控系统

风控系统采用分级处理机制，轻度触发发警告，重度触发强制平仓。

### 7.1 风控级别定义

```python
from enum import Enum


class RiskLevel(str, Enum):
    """风控级别"""
    NORMAL = "normal"      # 正常 - 无风控触发
    WARNING = "warning"    # 警告 - 发送通知，继续执行
    CRITICAL = "critical"  # 严重 - 强制平仓，停止策略


class RiskAction(str, Enum):
    """风控动作"""
    NONE = "none"              # 无动作
    WARN = "warn"              # 发送警告通知
    STOP_TRADING = "stop"      # 停止开新仓
    FORCE_CLOSE = "force_close"  # 强制平仓
```

### 7.2 风控规则配置

```python
@dataclass
class RiskRule:
    """风控规则"""
    name: str                 # 规则名称
    level: RiskLevel          # 风控级别
    threshold: float          # 触发阈值
    action: RiskAction        # 触发动作
    description: str = ""     # 规则描述


@dataclass
class RiskConfig:
    """风控配置"""

    # 账户级风控
    max_daily_loss_pct: float = 0.05       # 日最大亏损比例 (5%)
    max_drawdown_pct: float = 0.15         # 最大回撤比例 (15%)
    max_total_position_pct: float = 0.8    # 最大总仓位比例 (80%)

    # 策略级风控
    max_strategy_loss_pct: float = 0.03    # 单策略最大亏损 (3%)
    max_single_position_pct: float = 0.3   # 单仓位最大占比 (30%)

    # 警告阈值（达到此值发警告，达到最大值强制平仓）
    warning_ratio: float = 0.7             # 警告阈值 = 最大值 × 0.7


# 默认风控规则
DEFAULT_RISK_RULES = [
    RiskRule(
        name="daily_loss_warning",
        level=RiskLevel.WARNING,
        threshold=0.035,  # 3.5%
        action=RiskAction.WARN,
        description="日亏损达到警告阈值"
    ),
    RiskRule(
        name="daily_loss_critical",
        level=RiskLevel.CRITICAL,
        threshold=0.05,  # 5%
        action=RiskAction.FORCE_CLOSE,
        description="日亏损达到上限，强制平仓"
    ),
    RiskRule(
        name="max_drawdown_warning",
        level=RiskLevel.WARNING,
        threshold=0.10,  # 10%
        action=RiskAction.WARN,
        description="回撤达到警告阈值"
    ),
    RiskRule(
        name="max_drawdown_critical",
        level=RiskLevel.CRITICAL,
        threshold=0.15,  # 15%
        action=RiskAction.FORCE_CLOSE,
        description="回撤达到上限，强制平仓"
    ),
]
```

### 7.3 风控管理器

```python
@dataclass
class RiskCheckResult:
    """风控检查结果"""
    level: RiskLevel
    triggered_rules: List[RiskRule]
    recommended_action: RiskAction
    details: Dict[str, Any]


class RiskManager:
    """
    风控管理器 - 分级处理

    触发逻辑:
    - WARNING 级别: 发送警告通知，继续执行
    - CRITICAL 级别: 强制平仓，停止策略
    """

    def __init__(self, config: RiskConfig):
        self.config = config
        self.rules: List[RiskRule] = self._init_rules()
        self.daily_pnl: float = 0.0
        self.peak_equity: float = 0.0
        self.current_equity: float = 0.0

    def check_risk(
        self,
        account: "BaseAccount",
        positions: Dict[str, Any],
        trade_history: List["TradeResult"]
    ) -> RiskCheckResult:
        """
        执行风控检查

        Args:
            account: 账户对象
            positions: 当前持仓
            trade_history: 交易历史

        Returns:
            风控检查结果
        """
        triggered = []

        # 检查日亏损
        daily_loss_rule = self._check_daily_loss(trade_history)
        if daily_loss_rule:
            triggered.append(daily_loss_rule)

        # 检查最大回撤
        drawdown_rule = self._check_drawdown(account.balance)
        if drawdown_rule:
            triggered.append(drawdown_rule)

        # 检查仓位占比
        position_rule = self._check_position_ratio(account, positions)
        if position_rule:
            triggered.append(position_rule)

        # 确定最高级别和推荐动作
        if not triggered:
            return RiskCheckResult(
                level=RiskLevel.NORMAL,
                triggered_rules=[],
                recommended_action=RiskAction.NONE,
                details={}
            )

        max_level = max(r.level.value for r in triggered)
        max_action = max(r.action.value for r in triggered)

        return RiskCheckResult(
            level=RiskLevel(max_level),
            triggered_rules=triggered,
            recommended_action=RiskAction(max_action),
            details={
                "daily_pnl": self.daily_pnl,
                "current_drawdown": self._calculate_drawdown(),
            }
        )

    def _check_daily_loss(
        self,
        trade_history: List["TradeResult"]
    ) -> Optional[RiskRule]:
        """检查日亏损"""
        # 计算当日盈亏
        today_pnl = sum(
            t.pnl for t in trade_history
            if t.timestamp.date() == datetime.now().date()
        )
        self.daily_pnl = today_pnl

        daily_loss_pct = abs(today_pnl) / self.peak_equity if today_pnl < 0 else 0

        for rule in self.rules:
            if "daily_loss" in rule.name and daily_loss_pct >= rule.threshold:
                return rule
        return None

    def _check_drawdown(self, current_balance: float) -> Optional[RiskRule]:
        """检查最大回撤"""
        self.current_equity = current_balance
        if current_balance > self.peak_equity:
            self.peak_equity = current_balance

        drawdown = self._calculate_drawdown()

        for rule in self.rules:
            if "drawdown" in rule.name and drawdown >= rule.threshold:
                return rule
        return None

    def _calculate_drawdown(self) -> float:
        """计算当前回撤"""
        if self.peak_equity <= 0:
            return 0.0
        return (self.peak_equity - self.current_equity) / self.peak_equity

    def _check_position_ratio(
        self,
        account: "BaseAccount",
        positions: Dict[str, Any]
    ) -> Optional[RiskRule]:
        """检查仓位占比"""
        # 实现仓位风险检查
        pass

    def reset_daily(self):
        """每日重置（凌晨调用）"""
        self.daily_pnl = 0.0

    def _init_rules(self) -> List[RiskRule]:
        """初始化风控规则"""
        return DEFAULT_RISK_RULES.copy()
```

### 7.4 风控集成示例

```python
class BacktestEngine:
    def __init__(self, ...):
        self.risk_manager = RiskManager(risk_config)

    async def _execute_tick(self, ...):
        # 执行风控检查
        risk_result = self.risk_manager.check_risk(
            self.account, self.positions, self.trade_history
        )

        # 处理风控结果
        if risk_result.level == RiskLevel.CRITICAL:
            await self._force_close_all_positions()
            raise RiskControlTriggeredError(risk_result)

        elif risk_result.level == RiskLevel.WARNING:
            self._emit_warning(risk_result)

        # 继续执行策略...
```

---

## 八、配置管理

### 8.1 配置结构

```python
from dataclasses import dataclass, field
from typing import Optional
import yaml
import os


@dataclass
class DataCenterConfig:
    """数据中心配置"""
    base_url: str = "https://api.binance.com"
    futures_url: str = "https://fapi.binance.com"
    enable_cache: bool = True
    cache_ttl: int = 300              # 缓存过期时间（秒）
    timeout: float = 30.0             # 请求超时（秒）
    max_retries: int = 3              # 最大重试次数
    retry_delay: float = 1.0          # 重试延迟（秒）


@dataclass
class TradingConfig:
    """交易配置"""
    default_leverage: int = 10        # 默认杠杆
    default_position_pct: float = 0.1 # 默认仓位比例
    taker_fee: float = 0.0004         # taker 手续费
    maker_fee: float = 0.0002         # maker 手续费
    slippage: float = 0.0005          # 滑点


@dataclass
class EngineConfig:
    """引擎配置"""
    batch_size: int = 200             # 数据批量加载大小
    preload_enabled: bool = True      # 启用预加载
    max_speed: int = 999              # 最大回测速度
    default_indicators: List[str] = field(
        default_factory=lambda: ["ema_20", "ema_50", "macd", "rsi_14", "bollinger"]
    )


@dataclass
class SystemConfig:
    """系统总配置"""
    data_center: DataCenterConfig = field(default_factory=DataCenterConfig)
    trading: TradingConfig = field(default_factory=TradingConfig)
    engine: EngineConfig = field(default_factory=EngineConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)

    # 全局设置
    timezone: str = "Asia/Shanghai"
    log_level: str = "INFO"
    debug: bool = False

    @classmethod
    def from_yaml(cls, path: str) -> "SystemConfig":
        """从 YAML 文件加载配置"""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return cls(
            data_center=DataCenterConfig(**data.get("data_center", {})),
            trading=TradingConfig(**data.get("trading", {})),
            engine=EngineConfig(**data.get("engine", {})),
            risk=RiskConfig(**data.get("risk", {})),
            timezone=data.get("timezone", "Asia/Shanghai"),
            log_level=data.get("log_level", "INFO"),
            debug=data.get("debug", False),
        )

    @classmethod
    def from_env(cls) -> "SystemConfig":
        """从环境变量加载配置"""
        return cls(
            data_center=DataCenterConfig(
                base_url=os.getenv("DATA_CENTER_URL", "https://api.binance.com"),
                enable_cache=os.getenv("ENABLE_CACHE", "true").lower() == "true",
            ),
            trading=TradingConfig(
                default_leverage=int(os.getenv("DEFAULT_LEVERAGE", "10")),
            ),
            timezone=os.getenv("TIMEZONE", "Asia/Shanghai"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            debug=os.getenv("DEBUG", "false").lower() == "true",
        )

    def to_yaml(self, path: str):
        """导出配置到 YAML 文件"""
        data = {
            "data_center": self.data_center.__dict__,
            "trading": self.trading.__dict__,
            "engine": self.engine.__dict__,
            "risk": self.risk.__dict__,
            "timezone": self.timezone,
            "log_level": self.log_level,
            "debug": self.debug,
        }
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
```

### 8.2 配置文件示例

```yaml
# config.yaml
data_center:
  base_url: "https://api.binance.com"
  futures_url: "https://fapi.binance.com"
  enable_cache: true
  cache_ttl: 300
  timeout: 30.0
  max_retries: 3

trading:
  default_leverage: 10
  default_position_pct: 0.1
  taker_fee: 0.0004
  maker_fee: 0.0002
  slippage: 0.0005

engine:
  batch_size: 200
  preload_enabled: true
  max_speed: 999
  default_indicators:
    - ema_20
    - ema_50
    - macd
    - rsi_14
    - bollinger

risk:
  max_daily_loss_pct: 0.05
  max_drawdown_pct: 0.15
  max_strategy_loss_pct: 0.03
  max_single_position_pct: 0.3

timezone: "Asia/Shanghai"
log_level: "INFO"
debug: false
```

### 8.3 配置加载优先级

| 优先级 | 来源 | 说明 |
|--------|------|------|
| 1 (最高) | 代码传参 | 直接在代码中传入的配置 |
| 2 | 环境变量 | 以 `TRADING_` 为前缀的环境变量 |
| 3 | 配置文件 | `config.yaml` 或指定的配置文件 |
| 4 (最低) | 默认值 | dataclass 中定义的默认值 |

---

## 九、核心流程

### 9.1 回测执行流程

```
┌────────────────────────────────────────────────────────────────────────┐
│                        回测执行流程                                    │
└────────────────────────────────────────────────────────────────────────┘

1. 初始化阶段
   ┌─────────────────────────────────────────────────────────────────────┐
   │ 加载策略 → 获取数据需求 → 计算预热时间 → 加载预热数据             │
   │     ↓                                                              │
   │ 创建账户 → 初始化持仓管理器 → 创建流式数据加载器                  │
   └─────────────────────────────────────────────────────────────────────┘

2. Playback 循环
   ┌─────────────────────────────────────────────────────────────────────┐
   │ for tick in data_loader:                                           │
   │     ├─ 检查暂停/恢复状态                                           │
   │     ├─ 更新持仓盈亏（使用标记价格）                                │
   │     ├─ 检查止盈止损/强平                                           │
   │     ├─ 构建 StrategyContext                                        │
   │     ├─ strategy.execute(context) → StrategyResult                  │
   │     ├─ 解析 signals                                                │
   │     ├─ trader.execute_trade() → TradeResult                        │
   │     ├─ account.apply_trade_result()                                │
   │     ├─ 推送 tick 事件 (WebSocket)                                  │
   │     └─ 控制播放速度                                                │
   └─────────────────────────────────────────────────────────────────────┘

3. 结束阶段
   ┌─────────────────────────────────────────────────────────────────────┐
   │ 平仓所有持仓 → 计算统计指标 → 生成权益曲线 → 保存回测历史         │
   │     ↓                                                              │
   │ 推送 complete 事件 → 返回最终报告                                  │
   └─────────────────────────────────────────────────────────────────────┘
```

### 9.2 实时策略执行流程

```
┌────────────────────────────────────────────────────────────────────────┐
│                      实时策略执行流程                                  │
└────────────────────────────────────────────────────────────────────────┘

1. 初始化阶段
   ┌─────────────────────────────────────────────────────────────────────┐
   │ 加载策略 → 获取数据需求 → 加载初始 K线数据                        │
   │     ↓                                                              │
   │ 创建账户 (Virtual/Real) → 订阅 WebSocket 数据流                   │
   └─────────────────────────────────────────────────────────────────────┘

2. 事件驱动循环
   ┌─────────────────────────────────────────────────────────────────────┐
   │ on_kline_update(kline):                                            │
   │     ├─ 更新 market_data                                            │
   │     ├─ 构建 StrategyContext                                        │
   │     ├─ strategy.execute(context) → StrategyResult                  │
   │     ├─ 解析 signals                                                │
   │     │                                                              │
   │     ├─ [Paper 模式]                                                │
   │     │   └─ trader.execute_trade() → 模拟执行                       │
   │     │                                                              │
   │     ├─ [Live 模式]                                                 │
   │     │   └─ api_client.place_order() → 真实下单                     │
   │     │                                                              │
   │     ├─ 更新账户状态                                                │
   │     └─ 推送信号事件 (WebSocket)                                    │
   └─────────────────────────────────────────────────────────────────────┘

3. 停止阶段
   ┌─────────────────────────────────────────────────────────────────────┐
   │ 取消 WebSocket 订阅 → 保存执行记录 → 返回执行统计                 │
   └─────────────────────────────────────────────────────────────────────┘
```

### 9.3 数据流向图

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           数据流向                                       │
└──────────────────────────────────────────────────────────────────────────┘

外部数据源                    数据 Hub                      交易系统
┌─────────────┐          ┌─────────────────┐          ┌─────────────────┐
│ Binance API │ ───────> │ KlineService    │ ───────> │ Engine          │
│ (现货/合约)  │          │ IndicatorService│          │   ↓             │
└─────────────┘          │ CacheLayer      │          │ Strategy        │
                         └─────────────────┘          │   ↓             │
                                │                     │ Trader          │
                                │                     │   ↓             │
                                │                     │ Account         │
                                │                     └─────────────────┘
                                │                              │
                                └───────── 缓存命中 ───────────┘

WebSocket 实时流              实时引擎                   前端展示
┌─────────────┐          ┌─────────────────┐          ┌─────────────────┐
│ Binance WS  │ ───────> │ RealtimeEngine  │ ───────> │ WebSocket GW    │
│ (K线更新)    │          │   ↓             │          │   ↓             │
└─────────────┘          │ Strategy.execute│          │ 前端 UI         │
                         │   ↓             │          │ - 实时图表       │
                         │ 信号推送        │          │ - 交易记录       │
                         └─────────────────┘          └─────────────────┘
```

---

## 十、扩展指南

### 10.1 添加新交易类型

```python
# 1. 创建新的 Trader 类
class NewTrader(BaseTrader):
    def __init__(self):
        super().__init__(ContractType.NEW_TYPE)

    async def execute_trade(self, signal, price, account, config):
        # 实现交易逻辑
        pass

# 2. 创建对应的 Account 类（如需要）
class NewSimulatedAccount(BaseAccount):
    def apply_trade_result(self, trade_result):
        # 实现资金更新逻辑
        pass

# 3. 注册到 TradingService
self._traders[ContractType.NEW_TYPE] = NewTrader()
```

### 10.2 添加新数据源

```python
# 1. 创建新的 DataService 类
class NewExchangeService(DataCenterServiceBase):
    async def get_kline_data(self, request):
        # 实现数据获取逻辑
        pass

# 2. 在 DataCenterService 中集成
class DataCenterService:
    def __init__(self):
        self.new_exchange_service = NewExchangeService(base_url)
```

### 10.3 添加新技术指标

```python
# 1. 在 TALibIndicatorService 中添加静态方法
class TALibIndicatorService:
    @staticmethod
    def calculate_new_indicator(
        close: np.ndarray,
        period: int = 14
    ) -> np.ndarray:
        """计算新指标"""
        return talib.NEW_INDICATOR(close, timeperiod=period)

# 2. 在引擎的 _build_context 中添加计算
indicators["new_indicator"] = TALibIndicatorService.calculate_new_indicator(close)
```

### 10.4 交易所抽象层

为支持多交易所扩展，定义统一的交易所适配器接口。

```python
class ExchangeAdapter(ABC):
    """交易所适配器 - 统一接口"""

    def __init__(self, api_key: str = "", api_secret: str = ""):
        self.api_key = api_key
        self.api_secret = api_secret

    @abstractmethod
    async def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 100,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> List[List]:
        """
        获取 K 线数据

        Returns:
            标准化的 K 线数据列表
            [[open_time, open, high, low, close, volume, close_time, ...], ...]
        """
        pass

    @abstractmethod
    async def get_ticker(self, symbol: str) -> Dict[str, float]:
        """
        获取最新价格

        Returns:
            {"lastPrice": float, "markPrice": float, "indexPrice": float}
        """
        pass

    @abstractmethod
    async def get_balance(self) -> Dict[str, float]:
        """
        获取账户余额

        Returns:
            {"USDT": 10000.0, "BTC": 0.5, ...}
        """
        pass

    @abstractmethod
    async def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        下单

        Args:
            symbol: 交易对
            side: BUY / SELL
            order_type: MARKET / LIMIT
            quantity: 数量
            price: 价格（限价单必填）

        Returns:
            订单信息
        """
        pass

    @abstractmethod
    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        """取消订单"""
        pass

    @abstractmethod
    async def get_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """查询订单"""
        pass


class BinanceSpotAdapter(ExchangeAdapter):
    """Binance 现货适配器"""

    BASE_URL = "https://api.binance.com"

    async def get_klines(self, symbol, interval, limit=100, start_time=None, end_time=None):
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        # 调用 Binance API
        pass


class BinanceFuturesAdapter(ExchangeAdapter):
    """Binance U本位合约适配器"""

    BASE_URL = "https://fapi.binance.com"

    # 实现合约特定接口
    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """设置杠杆"""
        pass

    async def get_position(self, symbol: str) -> Dict[str, Any]:
        """获取持仓信息"""
        pass


# 未来扩展示例
# class OKXAdapter(ExchangeAdapter): ...
# class BybitAdapter(ExchangeAdapter): ...
```

#### 交易所适配器使用示例

```python
class DataCenterService:
    def __init__(self, exchange: str = "binance"):
        # 根据配置选择适配器
        self.adapter = self._create_adapter(exchange)

    def _create_adapter(self, exchange: str) -> ExchangeAdapter:
        adapters = {
            "binance": BinanceSpotAdapter,
            "binance_futures": BinanceFuturesAdapter,
            # "okx": OKXAdapter,
        }
        return adapters.get(exchange, BinanceSpotAdapter)()
```

---

## 附录

### A. 支持的时间间隔

| 间隔 | 说明 |
|------|------|
| 1m | 1分钟 |
| 3m | 3分钟 |
| 5m | 5分钟 |
| 15m | 15分钟 |
| 30m | 30分钟 |
| 1h | 1小时 |
| 2h | 2小时 |
| 4h | 4小时 |
| 6h | 6小时 |
| 8h | 8小时 |
| 12h | 12小时 |
| 1d | 1天 |
| 3d | 3天 |
| 1w | 1周 |
| 1M | 1月 |

### B. 错误码定义

| 错误码 | 说明 |
|--------|------|
| INSUFFICIENT_FUNDS | 资金不足 |
| INVALID_SIGNAL | 无效信号 |
| POSITION_NOT_FOUND | 持仓不存在 |
| STRATEGY_LOAD_ERROR | 策略加载失败 |
| DATA_FETCH_ERROR | 数据获取失败 |
| CIRCUIT_BREAKER_OPEN | 熔断器已打开 |
| RISK_CONTROL_TRIGGERED | 风控触发 |

### C. 技术依赖

| 依赖 | 版本要求 | 用途 |
|------|----------|------|
| Python | >=3.10 | 运行环境 |
| httpx | >=0.24 | 异步 HTTP 客户端 |
| tenacity | >=8.0 | 重试机制 |
| websockets | >=11.0 | WebSocket 客户端 |
| numpy | >=1.24 | 数值计算 |
| pandas | >=2.0 | 数据处理 |
| TA-Lib | >=0.4.28 | 技术指标计算 |
| pyyaml | >=6.0 | 配置文件解析 |

---

**文档版本**: v2.0
**基于项目**: binatms
**更新日期**: 2026-01-16
**主要更新**:
- 新增复合策略基类支持
- 新增信号处理规则
- 新增时区同步机制
- 新增 TA-Lib 技术指标计算服务
- 新增风控系统（分级处理）
- 新增配置管理模块
- 新增回测报告模型
- 新增交易所抽象层
- 移除 timeframe 参数，统一使用 interval
