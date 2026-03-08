---
name: release
description: 发布 XQTrader 新版本。执行完整的版本发布流程：检查工作区、运行测试、打 tag、构建、发布到 PyPI。当用户要求发布版本、打包发布、release 时使用此技能。
argument-hint: <版本号> [--dry] [--testpypi]，如 0.2.0、0.2.0 --dry、0.2.0 --testpypi
---

# XQTrader 版本发布流程

你正在执行 XQTrader 的版本发布。严格按照以下步骤顺序执行，每一步都必须通过后才能进入下一步。

## 参数解析

从用户输入中提取：
- `VERSION`：版本号（必须，SemVer 格式如 `0.2.0`、`1.0.0-beta.1`）
- `--dry`：仅验证不实际发布（可选）
- `--testpypi`：发布到 TestPyPI 而非正式 PyPI（可选）

如果用户未提供版本号，询问用户。可参考最近的 git tag 建议下一个版本：
- Bug 修复：patch +1（如 0.1.0 → 0.1.1）
- 新功能：minor +1（如 0.1.0 → 0.2.0）
- 破坏性变更：major +1（如 0.x.y → 1.0.0）

## 第1步：前置检查

依次检查以下条件，任何一项失败则停止并告知用户：

```bash
# 1.1 检查当前分支（应为 main 或 master）
git branch --show-current

# 1.2 检查工作区是否干净（不能有未提交变更）
git status --porcelain

# 1.3 检查 tag 是否已存在
git tag -l "v<VERSION>"

# 1.4 检查 uv 可用
uv --version
```

- 如果分支不是 main/master，**警告用户并确认**是否继续
- 如果工作区不干净，**停止**，提示用户先 commit
- 如果 tag 已存在，**停止**，提示用户选择其他版本号
- 如果是 `--dry` 模式，在每步输出中标注 `[DRY RUN]`

## 第2步：运行测试

```bash
uv run pytest -q
```

- 测试必须全部通过才能继续
- 如果有失败，停止发布并展示失败信息

## 第3步：创建 Git Tag

```bash
# 非 dry-run 时执行
git tag -a "v<VERSION>" -m "Release <VERSION>"
```

- Tag 格式固定为 `v<VERSION>`（如 `v0.2.0`）
- `--dry` 模式下跳过此步，输出 `[DRY RUN] 跳过 git tag`

## 第4步：清理旧构建

```bash
rm -rf dist/ build/ *.egg-info xqtrader.egg-info
```

## 第5步：构建

```bash
uv build
```

构建完成后验证：
- `dist/` 下应存在 `.tar.gz`（sdist）和 `.whl`（wheel）两个文件
- 文件名应包含版本号 `<VERSION>`（如 `xqtrader-0.2.0.tar.gz`）
- 如果版本号不干净（包含 `.post` 或 `+g` 后缀），说明 tag 未正确关联到当前 commit，**停止并排查**

## 第6步：发布

### 正式 PyPI（默认）
```bash
uv publish
```

### TestPyPI（--testpypi 模式）
```bash
uv publish --publish-url https://test.pypi.org/legacy/
```

### DRY RUN（--dry 模式）
不执行发布，输出验证结果和构建产物信息。

**重要：发布到正式 PyPI 前必须向用户确认。**

## 第7步：推送 Tag（可选）

发布成功后，询问用户是否推送 tag 到远程：

```bash
git push origin "v<VERSION>"
```

## 第8步：输出摘要

发布完成后输出：

```
发布完成!
  版本:  v<VERSION>
  PyPI:  pip install xqtrader==<VERSION>
  命令:  xqtrader --version / xqt --version
```

如果是 TestPyPI：
```
  安装测试: pip install -i https://test.pypi.org/simple/ xqtrader==<VERSION>
```

## 快捷方式

也可以直接调用发布脚本（脚本内置了所有步骤）：

```bash
./scripts/release.sh <VERSION> [--dry] [--testpypi]
```

## 版本管理规则

- 版本号由 `setuptools-scm` 从 git tag 自动生成
- **不要**手动编辑 `xqtrader/_version.py`，该文件由构建系统自动生成
- Tag 必须打在干净的 commit 上（无未提交变更），否则版本号会带后缀
- `pyproject.toml` 中的 `dynamic = ["version"]` 确保版本号从 tag 获取

## 错误处理

| 错误 | 原因 | 解决 |
|------|------|------|
| 版本号带 `.post0+g...` 后缀 | tag 未在当前 commit 上 | 确保先 commit 所有变更再打 tag |
| `uv publish` 认证失败 | 未配置 PyPI token | 运行 `uv publish --token <TOKEN>` 或设置 `UV_PUBLISH_TOKEN` 环境变量 |
| Tag 已存在 | 版本号重复 | 选择新版本号，或 `git tag -d v<VERSION>` 删除后重试 |
| 测试失败 | 代码问题 | 修复测试后重新发布 |

## 参考文件

- 发布脚本：`scripts/release.sh`
- 项目配置：`pyproject.toml`
- 版本文件（自动生成）：`xqtrader/_version.py`
