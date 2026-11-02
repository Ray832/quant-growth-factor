# -*- coding: utf-8 -*-
"""人工比对：平台输出 vs 本地参考结果。

两种参考目录，含义不同：

1) 平台格式目录（如 output/platform_full/）
   —— 由同一个单文件脚本在本地跑出，文件一一对应，应当逐位一致。
2) 本地分析目录（output/tables/）
   —— 由 src/ 的 P1/P2/P3 脚本产出，IC 序列与分层用的是 P1 口径（仅行业中性），
      与平台版的"行业+市值中性"不同，因此只有 IC 汇总与回归可以直接比。

用法：
    python scripts/compare_platform.py <平台out目录> <参考目录>
    python scripts/compare_platform.py out output/platform_full
    python scripts/compare_platform.py out output/tables
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


def diff(a: pd.Series, b: pd.Series, name: str) -> float:
    a, b = a.align(b)
    d = (a - b).abs()
    print(f"  {name:14s} n={int(d.notna().sum()):3d}  max|Δ|={d.max():.2e}")
    return float(d.max()) if d.notna().any() else 0.0


def compare_platform_dirs(plat: Path, ref: Path) -> float:
    print("参考目录为平台格式：逐文件比对（应逐位一致）")
    worst = 0.0
    for fname, keycol in (
        ("ic_summary.csv", "factor"),
        ("fdr_summary.csv", "factor"),
        ("layer_summary.csv", "factor"),
        ("regression_summary.csv", "factor"),
    ):
        a = pd.read_csv(plat / fname).set_index(keycol).sort_index()
        b = pd.read_csv(ref / fname).set_index(keycol).sort_index()
        common = [c for c in a.columns if c in b.columns and a[c].dtype.kind in "fc"]
        print(f"\n{fname}")
        for c in common:
            worst = max(worst, diff(a[c], b[c], c))
    print("\nic_series.csv")
    ia = pd.read_csv(plat / "ic_series.csv", index_col=0, parse_dates=True).sort_index()
    ib = pd.read_csv(ref / "ic_series.csv", index_col=0, parse_dates=True).sort_index()
    for c in ia.columns:
        if c in ib.columns:
            worst = max(worst, diff(ia[c], ib[c], c))
    return worst


def compare_src_tables(plat: Path, ref: Path) -> float:
    print("参考目录为 src 分析表：只比对 IC 汇总与回归（其余口径不同）")
    worst = 0.0
    a = pd.read_csv(plat / "ic_summary.csv").set_index("factor").sort_index()
    b = pd.read_csv(ref / "fdr_summary.csv").set_index("factor").sort_index()
    print("\nIC 汇总")
    worst = max(worst, diff(a["mean"], b["ic_mean"], "IC"))
    worst = max(worst, diff(a["t"], b["t"], "t 值"))

    r = pd.read_csv(plat / "regression_summary.csv").set_index("factor").sort_index()
    s = pd.read_csv(ref / "regression_summary.csv").set_index("factor").sort_index()
    print("\n回归")
    worst = max(worst, diff(r["abs_t_mean"], s["abs_t_mean"], "|t| 均值"))
    worst = max(worst, diff(r["beta_t"], s["beta_t_stat"], "beta t 值"))
    print("\n（跳过 ic_series / layer：本地表是 P1 行业中性口径，与平台版不可直接比）")
    return worst


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    plat, ref = Path(sys.argv[1]), Path(sys.argv[2])
    if not (plat / "ic_summary.csv").exists():
        sys.exit(f"平台目录缺少 ic_summary.csv: {plat}")

    # 用 fdr_summary 的列名区分两种参考目录：
    #   平台格式 → 列名 mean/t/p/p_adj
    #   src 表   → 列名 ic_mean/t/p/p_adj
    is_src = False
    ref_fdr = ref / "fdr_summary.csv"
    if ref_fdr.exists():
        cols = pd.read_csv(ref_fdr, nrows=0).columns
        is_src = "ic_mean" in cols

    worst = compare_src_tables(plat, ref) if is_src else compare_platform_dirs(plat, ref)

    print(f"\n最大绝对差：{worst:.3e}")
    print("判定：" + ("一致 ✅" if worst < 1e-9 else ("可接受（<1e-6）" if worst < 1e-6 else "存在差异，需排查")))


if __name__ == "__main__":
    main()
