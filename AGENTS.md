# AGENTS

Purpose
- 为量化交易引擎 QuantTrader 提供 agentic 编码指导。
- 变更保持最小化，遵循既有结构与命名。

Repository snapshot
- Python 包位于 `quanttrader/`。
- 测试位于 `tests/`。
- 示例位于 `examples/`。
- 配置集中在 `quanttrader/config/`。
- 当前无格式化/静态检查配置文件。

Project layout
- `quanttrader/strategies/`: 策略基类与加载器。
- `quanttrader/engine/`: 回测/实时执行引擎。
- `quanttrader/traders/`: 交易执行器。
- `quanttrader/accounts/`: 模拟账户与保证金逻辑。
- `quanttrader/data/`: 数据中心与交易所适配器。
- `quanttrader/risk/`: 风控规则与风险等级。
- `quanttrader/reports/`: 回测报告与记录。
- `quanttrader/utils/`: 通用工具函数。

Entry points
- 主入口: `main.py`。
- 运行示例: `examples/simple_backtest.py`。

Required environment
- Python >= 3.11 (见 `pyproject.toml`)。
- 依赖管理: `uv`。
- 可选开发依赖在 `project.optional-dependencies.dev`。

Build, lint, test commands
- 安装依赖: `uv sync --dev`。
- 运行全部测试: `uv run pytest`。
- 运行单测文件: `uv run pytest tests/test_data_center.py -v`。
- 运行单测用例: `uv run pytest tests/test_data_center.py -k test_kline_cache -v`。
- 仅运行异步测试: `uv run pytest -k "async" -v`。
- 运行单个示例: `uv run python examples/simple_backtest.py`。
- 运行主程序: `uv run python main.py`。
- Lint/format: 仓库未配置，请勿自行引入或假设存在。

Cursor/Copilot rules
- 未发现 `.cursor/rules/`、`.cursorrules`、`.github/copilot-instructions.md`。

Architecture cues
- 数据流: DataCenterService -> Engine -> Strategy -> Trader -> Account -> Risk -> Report。
- 基类集中在 `quanttrader/*/base.py`。
- MVP 以单标的回测闭环为主。

Code style: general
- 新模块优先包含 `from __future__ import annotations`。
- 常用数据结构使用 `@dataclass`。
- 固定选项使用 `Enum` 子类。
- 全面使用类型标注，保持与现有风格一致。
- 函数保持小而单一职责。
- 中文注释/文档较常见，保持简短、直接。

Imports
- 顺序: 标准库 -> 第三方 -> 本地包。
- 避免通配符导入。
- `quanttrader` 内使用绝对导入。
- 同模块的多个导入放在同一行。

Formatting
- 无统一格式化工具，遵循现有文件格式。
- 行宽建议 88-100 字符内。
- 逻辑段落之间保留空行。
- 多行参数采用竖直对齐风格。

Documentation
- 公共类/函数建议提供简短 docstring。
- 中文文档较多，保持直接、少废话。
- 行为变更时同步更新文档字符串。

Configuration and paths
- 配置文件优先放在 `quanttrader/config/`。
- 文件路径使用 `pathlib.Path`，避免硬编码绝对路径。
- 示例脚本保持可直接运行，避免默认访问真实网络。

Types and data models
- DTO 使用 `@dataclass`。
- 避免可变默认参数，使用 `field(default_factory=...)`。
- 可空值使用 `Optional[T]`。
- 元数据字段使用 `Dict[str, Any]`。

Naming conventions
- 类: `PascalCase`。
- 函数/变量: `snake_case`。
- 常量: `UPPER_SNAKE_CASE`。
- Enum 值: 使用小写字符串或既有枚举名。
- 文件: `snake_case.py`。

Error handling
- 非法参数: `TypeError` 或 `ValueError`。
- 非法状态: `RuntimeError`。
- 捕获异常仅用于补充上下文或记录信息，必要时重新抛出。
- 避免静默失败；需要时显式返回 `None`。

Async patterns
- 数据层多为异步 API，优先使用 `async with`。
- 避免在 async 流程中使用阻塞调用（测试例外）。
- 若新增 async 代码，确保调用端可 await。

Testing patterns
- 使用 pytest；测试函数为普通函数。
- 异步测试使用 `pytest.mark.asyncio`。
- 依赖真实网络的测试使用 `@pytest.mark.skip` 并说明原因。
- 保持测试可重复，避免依赖实时行情。

Strategy conventions
- `StrategyResult` 必须包含 `signals` 列表。
- 事件合约信号常用 UP/DOWN/HOLD。
- 永续合约信号常用 LONG/SHORT/CLOSE_*。
- 交易器允许 LONG/SHORT/BUY/SELL 兼容映射。

Futures conventions
- 使用 `FuturesSimulatedAccount` 与 `HedgePositionManager`。
- 保证金通过 `lock_margin` / `release_margin` 管理。
- 盈亏计算遵循多仓/空仓方向逻辑。

Data conventions
- `DataCenterService` 负责数据获取。
- 适配器规范化交易对，如 `BTCUSDT` -> `BTC/USDT`。
- 新适配器遵循现有接口命名。

Common file references
- 策略基类: `quanttrader/strategies/base.py`。
- 引擎基类: `quanttrader/engine/base.py`。
- 数据中心: `quanttrader/data/base.py`。
- 风控基类: `quanttrader/risk/base.py`。
- 交易器: `quanttrader/traders/*.py`。

Change checklist
- 保持公开 API 兼容，除非明确要求变更。
- 行为变更需同步更新文档字符串。
- 新逻辑尽量补充测试。
- 避免新增依赖，除非业务需要。

Notes for agents
- 不要假设存在 formatter/linter。
- 工作区可能是脏的，勿回滚不相关改动。
- 重构前先阅读附近代码以保持一致性。
- 新增文件保持 ASCII，除非已有非 ASCII 约定。
