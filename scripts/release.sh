#!/usr/bin/env bash
#
# XQTrader 发布脚本
#
# 用法:
#   ./scripts/release.sh 0.2.0          # 发布 v0.2.0
#   ./scripts/release.sh 0.2.0 --dry    # 仅验证，不实际发布
#   ./scripts/release.sh 0.2.0 --testpypi  # 发布到 TestPyPI
#

set -euo pipefail

# ─── 颜色 ───
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
DIM='\033[2m'
RESET='\033[0m'

info()  { echo -e "${GREEN}[INFO]${RESET} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${RESET} $*"; }
error() { echo -e "${RED}[ERROR]${RESET} $*"; exit 1; }

# ─── 参数解析 ───
VERSION="${1:-}"
DRY_RUN=false
USE_TESTPYPI=false

for arg in "$@"; do
    case "$arg" in
        --dry)      DRY_RUN=true ;;
        --testpypi) USE_TESTPYPI=true ;;
    esac
done

if [[ -z "$VERSION" || "$VERSION" == --* ]]; then
    echo "用法: $0 <version> [--dry] [--testpypi]"
    echo ""
    echo "示例:"
    echo "  $0 0.2.0            # 发布 v0.2.0 到 PyPI"
    echo "  $0 0.2.0 --dry      # 仅验证，不发布"
    echo "  $0 0.2.0 --testpypi # 发布到 TestPyPI"
    exit 1
fi

# 验证版本号格式 (SemVer)
if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$ ]]; then
    error "版本号格式无效: $VERSION (应为 SemVer, 如 0.2.0 或 1.0.0-beta.1)"
fi

TAG="v$VERSION"

# ─── 前置检查 ───
info "发布前检查..."

# 检查是否在 git 仓库
git rev-parse --is-inside-work-tree > /dev/null 2>&1 || error "不在 git 仓库中"

# 检查当前分支
BRANCH=$(git branch --show-current)
if [[ "$BRANCH" != "main" && "$BRANCH" != "master" ]]; then
    warn "当前分支是 '$BRANCH'，不是 main/master"
    read -p "确认继续? [y/N] " -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]] || exit 1
fi

# 检查工作区是否干净
if [[ -n "$(git status --porcelain)" ]]; then
    error "工作区有未提交的变更，请先 commit"
fi

# 检查 tag 是否已存在
if git tag -l "$TAG" | grep -q "$TAG"; then
    error "Tag $TAG 已存在"
fi

# 检查工具可用性
command -v uv >/dev/null 2>&1 || error "需要 uv，请安装: https://docs.astral.sh/uv/"

info "版本: $VERSION"
info "Tag:   $TAG"
info "分支:  $BRANCH"
$DRY_RUN && info "模式: DRY RUN (不会实际发布)"

# ─── 运行测试 ───
info "运行测试..."
uv run pytest -q || error "测试未通过"

# ─── 打 Tag ───
info "创建 tag: $TAG"
if $DRY_RUN; then
    info "(dry run) 跳过 git tag"
else
    git tag -a "$TAG" -m "Release $VERSION"
fi

# ─── 清理旧构建 ───
info "清理旧构建..."
rm -rf dist/ build/ *.egg-info xqtrader.egg-info

# ─── 构建 ───
info "构建包..."
if $DRY_RUN; then
    # dry run 也实际构建，用于验证
    git tag "$TAG" 2>/dev/null || true  # 临时 tag 用于构建
    uv build
    git tag -d "$TAG" 2>/dev/null || true  # 清理临时 tag
else
    uv build
fi

# 验证构建产物
SDIST=$(ls dist/*.tar.gz 2>/dev/null | head -1)
WHEEL=$(ls dist/*.whl 2>/dev/null | head -1)

[[ -f "$SDIST" ]] || error "未找到 sdist (.tar.gz)"
[[ -f "$WHEEL" ]] || error "未找到 wheel (.whl)"

info "构建产物:"
echo -e "  ${DIM}$SDIST${RESET}"
echo -e "  ${DIM}$WHEEL${RESET}"

# 验证版本号是否正确嵌入
if [[ "$SDIST" != *"$VERSION"* ]]; then
    warn "sdist 文件名不包含版本号 $VERSION，可能 tag 未正确关联"
fi

# ─── 发布 ───
if $DRY_RUN; then
    info "(dry run) 跳过发布"
    info "验证完成，可以正式运行:"
    echo -e "  ${GREEN}$0 $VERSION${RESET}"
else
    if $USE_TESTPYPI; then
        info "发布到 TestPyPI..."
        uv publish --publish-url https://test.pypi.org/legacy/
        info "已发布到 TestPyPI"
        echo -e "  安装测试: ${DIM}pip install -i https://test.pypi.org/simple/ xqtrader==$VERSION${RESET}"
    else
        info "发布到 PyPI..."
        read -p "确认发布 $TAG 到 PyPI? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            uv publish
            info "已发布到 PyPI"
            echo -e "  安装: ${DIM}pip install xqtrader==$VERSION${RESET}"
        else
            warn "已取消发布 (tag $TAG 已创建，如需撤销: git tag -d $TAG)"
            exit 0
        fi
    fi

    # 推送 tag
    read -p "推送 tag 到远程仓库? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git push origin "$TAG"
        info "Tag 已推送"
    fi
fi

echo ""
info "完成!"
