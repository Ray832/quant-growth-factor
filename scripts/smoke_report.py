# -*- coding: utf-8 -*-
"""小样本因子流水线演示（不是正式结果，用于验证链路可用性）。

用法：
    & 'E:\\量化研报复现\\env.cmd' scripts\\smoke_report.py --n 200

输出：
    output/smoke_summary.md   因子 IC 汇总与分层表现
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import config, data, evaluate, factors, preprocess  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200, help="股票数（小样本演示）")
    ap.add_argument("--start", default="2020-01-01")
    args = ap.parse_args()

    raw = data.load_panel()
    pool = data.filter_pool(raw)

    recent = pool[pool["date"] >= args.start]
    top = (recent.groupby("instrument")["close"].count()
           .sort_values(ascending=False).head(args.n).index)
    sub = pool[pool["instrument"].isin(top)].copy()

    wide = data.to_wide(sub)
    ind = wide["sw2021_level1_name"]
    fac = {k: preprocess.process(v, industry=ind)
           for k, v in factors.build_factors(wide).items()}

    dates = [d for d in wide["close"].index if d >= pd.Timestamp(args.start)]
    fac = {k: v.loc[dates] for k, v in fac.items()}
    fwd = evaluate.forward_return(wide["close"]).loc[dates]
    ind = ind.loc[dates]

    rows = []
    for name in config.FACTORS:
        ic = evaluate.ic_series(fac[name], fwd)
        st = evaluate.ic_stats(ic)
        rows.append({"factor": name, **st})
    ic_tbl = pd.DataFrame(rows)

    lines = []
    lines.append(f"# 小样本流水线自检（{args.n} 只股票，{dates[0]:%Y-%m} ~ {dates[-1]:%Y-%m}）\n")
    lines.append(f"- 截面数：{len(dates)}")
    lines.append(f"- 平均每期股票数：{int(fwd.notna().sum(axis=1).mean())}\n")

    lines.append("## 1. 因子 IC\n")
    lines.append("| 因子 | IC 均值 | IC 标准差 | IR | IC>0 占比 | |IC|>0.02 |")
    lines.append("|---|---|---|---|---|---|")
    for _, r in ic_tbl.iterrows():
        lines.append(
            f"| {r['factor']} | {r['mean']:+.4f} | {r['std']:.4f} | {r['ir']:+.3f} "
            f"| {r['positive_ratio']:.1%} | {r['abs_gt_002']:.1%} |"
        )

    lines.append("\n## 2. 分层回测（5 层，行业内排序，等权）\n")
    lines.append("| 因子 | TOP 年化 | TOP 夏普 | 多空年化 | 多空夏普 | 多空回撤 | 单调性(秩相关) |")
    lines.append("|---|---|---|---|---|---|---|")
    detail = {}
    for name in config.FACTORS[:3] + ["ROE_G_ttm"]:
        lay = evaluate.layer_returns(fac[name], fwd, ind, n=5)
        ls = evaluate.long_short(lay)
        p_top = evaluate.perf_stats(lay[0])
        p_ls = evaluate.perf_stats(ls)
        mean_by_layer = lay.mean()
        # 层号 0=最高因子组；相关系数为负说明高因子组收益更高，取负号使"正=符合预期"
        mono = -mean_by_layer.corr(pd.Series(range(5), index=mean_by_layer.index),
                                   method="spearman")
        detail[name] = lay
        lines.append(
            f"| {name} | {p_top['ann_return']:.1%} | {p_top['sharpe']:.2f} "
            f"| {p_ls['ann_return']:+.1%} | {p_ls['sharpe']:+.2f} "
            f"| {p_ls['max_drawdown']:.1%} | {mono:+.2f} |"
        )

    out_dir = ROOT / "output"
    out_dir.mkdir(exist_ok=True)
    path = out_dir / "smoke_summary.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\n已保存: {path}")

    # 分层月均收益（供报告引用）
    print("\n分层月均收益:")
    for name, lay in detail.items():
        print(f"  {name}: " + ", ".join(f"L{i}={lay[i].mean():+.3%}" for i in range(5)))


if __name__ == "__main__":
    main()
