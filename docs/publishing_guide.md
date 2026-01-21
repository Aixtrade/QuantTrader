# 发布与版本管理指南

适用范围：将项目作为 Python 库（pip/uv 可安装）发布与维护的最佳实践，包含配置要点与发布流程。

## 1. 项目配置最佳实践
- 包元数据
  - `pyproject.toml` 使用 PEP 621，设置 `name/description/readme/license/authors/dependencies`，`dynamic = ["version"]` 由 `setuptools-scm` 生成。
  - `packages = ["quanttrader"]` 或自动发现；如有 CLI，配置 `[project.scripts]`。
  - Python 版本下限：`requires-python = ">=3.10"`（按需要调整）。
- 依赖管理
  - 运行时依赖放 `dependencies`；开发/测试工具放 `optional-dependencies`（如 `dev`，包含 `pytest`, `setuptools-scm`）。
  - 使用 `uv lock` 固定版本，`uv sync --extra dev` 安装开发集。
- 版本来源（已选方案：`setuptools-scm`）
  - 在 `pyproject.toml` 声明 `[build-system]` 使用 `setuptools` 与 `setuptools-scm`；`[tool.setuptools_scm]` 控制版本写入 `quanttrader/_version.py`。
  - 版本由 git tag `vX.Y.Z` 推导；无 tag 时使用后缀（node-and-date）。
- 配置加载
  - 提供显式配置对象（dataclass），支持 `from_dict/from_env/from_yaml`；避免 import 时读取环境变量或写全局状态。
  - 默认配置应安全保守（禁用 Live 交易、启用超时/重试上限、日志级别 INFO）。
- 包含资源
  - 确保 `README.md`、`LICENSE`、`CHANGELOG.md`、必要的模板文件在构建中包含。
- 构建与发布工具
  - 构建：`uv build`（或 `python -m build`）。
  - 发布：`uv publish`（或 `twine upload dist/*`）。

## 2. 发布前检查清单
- 代码质量：`uv run pytest`（或最小 smoke）、类型检查/ lint（如配置则运行）。
- 依赖：确认运行时依赖最小化；dev 工具在 `optional-dependencies.dev`；`uv lock` 已更新。
- 版本：确认 git tag 将要发布的版本；`CHANGELOG.md` 已更新。
- 文档：`README`/示例与当前 API/CLI 一致。
- 安全：Live 模式默认关闭；无敏感凭据进入仓库。

## 3. 发布流程（基于 setuptools-scm）
1) 更新变更日志：`CHANGELOG.md` 记录本次发布。
2) 锁定依赖：`uv lock`（如依赖有变）。
3) 本地验证：`uv run pytest`，必要时 `uv run mypy`/lint（若配置）。
4) 构建：`uv build`。
5) 打 tag：`git tag vX.Y.Z`，`git push --tags`。
6) 发布：`uv publish`（或 `twine upload dist/*`）。

## 4. 版本号策略与分支
- 采用 SemVer：
  - PATCH：向后兼容修复。
  - MINOR：向后兼容的新功能。
  - MAJOR：破坏性变更。
- 预发布：`X.Y.ZaN/bN/rcN` 用于候选测试。
- 分支建议：`main` 可发布；功能分支开发，发布由 tag 驱动。

## 5. 常用命令速查
- 安装（用户）：`uv add quanttrader` 或 `pip install quanttrader`。
- 开发安装：`uv sync --extra dev`。
- 运行示例：`uv run python examples/simple_backtest.py`。
- 构建：`uv build`。
- 发布：`uv publish`（或 `twine upload dist/*`）。

## 6. CI 对齐
- `.github/workflows/ci.yml`：checkout → setup-python → 安装 uv → `uv sync --extra dev` → `uv run pytest` → `uv build`。

## 7. 安全与合规提醒
- 不要在仓库中提交 API Key/Secrets；使用环境变量或秘密管理服务注入。
- 发布前检查依赖许可证；确保 README/许可证/CHANGELOG 随包分发。
- Live 交易默认关闭，启用需显式配置；提供模拟/回测为默认模式。
