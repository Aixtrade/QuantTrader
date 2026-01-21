# AGENTS

Purpose
- Guide agentic coding tools for QuantTrader.
- Keep changes minimal and aligned with existing patterns.

Repository snapshot
- Python package lives in `quanttrader/`.
- Tests live in `tests/`.
- Examples live in `examples/`.
- Configuration is minimal; no formatter/linter configs detected.

Required environment
- Python >= 3.11 (see `pyproject.toml`).
- Dependency manager: `uv`.
- Optional deps for dev/testing live in `project.optional-dependencies.dev`.

Build, lint, test commands
- Install deps: `uv sync --dev`.
- Run all tests: `uv run pytest`.
- Run one test file: `uv run pytest tests/test_data_center.py -v`.
- Run one test function: `uv run pytest tests/test_data_center.py -k test_kline_cache -v`.
- Run async tests only: `uv run pytest -k "async" -v`.
- Run a single example: `uv run python examples/simple_backtest.py`.
- Run main entry: `uv run python main.py`.
- Lint/format: not configured in repo; do not invent tools.

Cursor/Copilot rules
- No `.cursor/rules/`, `.cursorrules`, or `.github/copilot-instructions.md` found.

Architecture cues
- Strategy -> Engine -> Trader -> Account -> Risk -> Report.
- Base abstractions in `quanttrader/*/base.py`.
- Data access via `DataCenterService` and adapters.
- MVP is single symbol backtest flow.

Code style: general
- Use `from __future__ import annotations` in new modules.
- Prefer dataclasses for DTOs (`@dataclass`).
- Use `Enum` subclasses for fixed choices.
- Type hints are expected; use `Optional`, `Dict`, `List`, `Tuple`.
- Keep functions small and single-purpose.
- Chinese docstrings and comments are common; keep them short.

Imports
- Standard library first, third-party second, local imports last.
- Keep imports explicit; avoid wildcard imports.
- Prefer absolute imports within `quanttrader` package.
- Group related imports from same module on one line.

Formatting
- No formatter configured; match existing formatting style.
- Keep line length reasonable (around 88-100 chars).
- Use blank lines between logical sections.
- Align parameters vertically when multi-line.

Types and data models
- Use dataclasses for plain data containers.
- Avoid mutable default arguments; use `field(default_factory=...)`.
- Use `Optional[T]` for nullable values.
- Use `Dict[str, Any]` for flexible metadata bags.

Naming conventions
- Classes: `PascalCase`.
- Functions and variables: `snake_case`.
- Constants: `UPPER_SNAKE_CASE`.
- Enum values: lower snake case strings.
- Files: `snake_case.py`.

Error handling
- Raise `TypeError` or `ValueError` for invalid input.
- Raise `RuntimeError` for invalid state (e.g., not connected).
- Catch exceptions only to add context or record metrics; re-raise.
- Avoid silent failures; return `None` explicitly when used.

Async patterns
- Data layer is async; prefer `async with` for services.
- Base engine `run` returns `AsyncGenerator` events.
- Avoid blocking calls inside async flows (except tests).

Testing patterns
- Use pytest classes (`class TestX`) with plain functions.
- Async tests use `pytest.mark.asyncio`.
- Network tests are marked `@pytest.mark.skip` with a reason.
- Keep tests deterministic; use small sleeps only for time-based logic.

Project-specific guidelines
- Strategy API returns `StrategyResult` with `signals` list.
- Signal action values include LONG/SHORT/CLOSE_* for futures; events use UP/DOWN/HOLD.
- Events trader accepts LONG/SHORT/BUY/SELL as aliases for UP/DOWN.
- Risk manager uses WARNING/CRITICAL levels and actions.
- Futures account uses `lock_margin` / `release_margin`.
- Data adapters normalize symbols like `BTCUSDT` -> `BTC/USDT`.

Common file references
- Strategy base: `quanttrader/strategies/base.py`.
- Engine base: `quanttrader/engine/base.py`.
- Data center: `quanttrader/data/base.py`.
- Risk: `quanttrader/risk/base.py`.
- Traders: `quanttrader/traders/*.py`.

Change checklist
- Keep public APIs backward-compatible unless asked.
- Update docstrings when changing behavior.
- Add tests for new logic where practical.
- Avoid adding new dependencies unless required.

Notes for agents
- Do not assume lint/format tooling exists.
- Do not change unrelated files in a dirty worktree.
- Read nearby code before making refactors.
- Use ASCII for new files unless the repo already uses non-ASCII.
