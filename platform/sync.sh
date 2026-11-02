#!/usr/bin/env bash
# 平台端同步脚本：优先 git pull；没有 git 就下载 tarball 覆盖代码。
#
# 用法：
#   bash platform/sync.sh                 # 默认目录 ~/work/quant-growth-factor
#   bash platform/sync.sh /path/to/repo   # 指定目录
#
# 说明：仓库里只有代码、文档、测试，没有数据；覆盖不会动到 bq_export_v41/ 等本地数据目录。

set -euo pipefail

REPO="Ray832/quant-growth-factor"
BRANCH="main"
DIR="${1:-$HOME/work/quant-growth-factor}"

echo "==> 目标目录: $DIR"

if command -v git >/dev/null 2>&1 && [ -d "$DIR/.git" ]; then
    echo "==> 检测到 git，执行 pull"
    cd "$DIR"
    git pull --ff-only
    echo "==> 完成（git）"
    exit 0
fi

echo "==> 未检测到可用的 git，改用 tarball"
mkdir -p "$DIR"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

URL="https://github.com/${REPO}/archive/refs/heads/${BRANCH}.tar.gz"
echo "==> 下载 $URL"
if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$URL" -o "$TMP/repo.tar.gz"
elif command -v wget >/dev/null 2>&1; then
    wget -q "$URL" -O "$TMP/repo.tar.gz"
else
    echo "!! curl 和 wget 都不可用，请手动下载 zip 上传" >&2
    exit 1
fi

tar -xzf "$TMP/repo.tar.gz" -C "$TMP"
SRC="$(find "$TMP" -maxdepth 1 -type d -name 'quant-growth-factor-*' | head -n 1)"
if [ -z "$SRC" ]; then
    echo "!! 解压后未找到源码目录" >&2
    exit 1
fi

cp -rf "$SRC"/. "$DIR"/
echo "==> 完成（tarball）-> $DIR"
echo "==> 提示：没有 .git 目录，无法用 git pull；下次仍走 tarball。"
