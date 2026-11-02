# -*- coding: utf-8 -*-
"""轻量备份与恢复（替代 Git 的简化方案）。

用法：
    python scripts/backup.py                    # 备份 src/ scripts/ tests/ 到 .backup/<时间戳>/
    python scripts/backup.py --tag before-p2    # 带标签
    python scripts/backup.py --list             # 列出备份
    python scripts/backup.py --restore 20261102_201500   # 恢复

规则：
    · 只备份代码与配置，不备份数据（数据只读，误删用导出脚本重导）；
    · 默认保留最近 10 份，超出自动删除最旧；
    · 恢复前会把当前状态再备份一次，避免"恢复即丢失"。
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKUP_DIR = ROOT / ".backup"
TARGETS = ["src", "scripts", "tests", "README.md", "env.cmd"]
KEEP = 10


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def backup(tag: str | None = None) -> Path:
    name = _stamp() + (f"_{tag}" if tag else "")
    dest = BACKUP_DIR / name
    dest.mkdir(parents=True, exist_ok=True)

    count = 0
    for rel in TARGETS:
        src = ROOT / rel
        if not src.exists():
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(src, target)
        count += 1

    _prune()
    print(f"已备份 {count} 项 -> {dest}")
    return dest


def _prune():
    if not BACKUP_DIR.exists():
        return
    items = sorted([p for p in BACKUP_DIR.iterdir() if p.is_dir()])
    for old in items[:-KEEP]:
        shutil.rmtree(old, ignore_errors=True)
        print(f"清理旧备份: {old.name}")


def list_backups():
    if not BACKUP_DIR.exists():
        print("还没有备份")
        return
    for p in sorted(BACKUP_DIR.iterdir()):
        if p.is_dir():
            size = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
            print(f"{p.name}  {size/1024:.0f} KB")


def restore(name: str):
    src = BACKUP_DIR / name
    if not src.exists():
        print(f"备份不存在: {src}")
        sys.exit(1)

    # 恢复前先给当前状态做一次备份
    safety = backup("prerestore")
    print(f"当前状态已备份到: {safety}")

    for rel in TARGETS:
        s = src / rel
        if not s.exists():
            continue
        d = ROOT / rel
        if d.exists():
            if d.is_dir():
                shutil.rmtree(d)
            else:
                d.unlink()
        if s.is_dir():
            shutil.copytree(s, d)
        else:
            shutil.copy2(s, d)
        print(f"已恢复: {rel}")
    print(f"完成。回滚这次恢复可用: python scripts/backup.py --restore {safety.name}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default=None)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--restore", default=None)
    args = ap.parse_args()

    if args.list:
        list_backups()
    elif args.restore:
        restore(args.restore)
    else:
        backup(args.tag)


if __name__ == "__main__":
    main()
