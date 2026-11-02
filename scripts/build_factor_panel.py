# -*- coding: utf-8 -*-
"""P1：构建全样本因子面板，并输出第一版 IC / 分层汇总。

输出：
    output/factors/<factor>.csv.gz      12 个因子（宽表，原始值）
    output/tables/ic_series.csv         IC 时间序列（date × factor）
    output/tables/ic_summary.csv        IC 汇总（均值/标准差/IR/胜率）
    output/tables/layer_summary.csv     5 层回测汇总
    output/logs/run_*.md                运行日志

用法：
    & 'E:\\量化研报复现\\env.cmd' scripts\\build_factor_panel.py
"""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import config, data, evaluate, factors, preprocess  # noqa: E402


def log(msg, lines):
    print(msg)
    lines.append(msg)


def main():
    t0 = time.time()
    lines = []
    now = datetime.now()

    log(f"# P1 因子面板构建 {now:%Y-%m-%d %H:%M:%S}", lines)

    raw = data.load_panel()
    log(f"读入 {len(raw):,d} 行，{raw['date'].nunique()} 个截面", lines)

    pool = data.filter_pool(raw)
    pool = data.apply_next_day_suspension(pool)
    log(f"股票池过滤后 {len(pool):,d} 行，{pool['instrument'].nunique():,d} 只（含次日停牌剔除）", lines)

    wide = data.to_wide(pool)
    ind = wide["sw2021_level1_name"]
    close = wide["close"]
    log(f"宽表字段 {len(wide)} 个", lines)

    fac_raw = factors.build_factors(wide)
    log(f"因子 {len(fac_raw)} 个", lines)

    # 评估期切片
    start, end = pd.Timestamp(config.EVAL_START), pd.Timestamp(config.EVAL_END)
    dates = [d for d in close.index if start <= d <= end]
    log(f"评估期 {dates[0]:%Y-%m-%d} ~ {dates[-1]:%Y-%m-%d}，{len(dates)} 个截面", lines)

    out_f = config.OUT_DIR / "factors"
    out_f.mkdir(parents=True, exist_ok=True)
    out_t = config.OUT_DIR / "tables"
    out_t.mkdir(parents=True, exist_ok=True)

    fwd = evaluate.forward_return(close).loc[dates]
    ind_eval = ind.loc[dates]

    ic_rows, ic_all, layer_rows = [], {}, []

    for name in config.FACTORS:
        f = fac_raw[name].loc[dates]
        f.to_csv(out_f / f"{name}.csv.gz", compression="gzip")

        # 行业中性 + 去极值 + 标准化，用于检验
        p = preprocess.process(f, industry=ind_eval, k=config.MAD_K)

        ic = evaluate.ic_series(p, fwd)
        ic_all[name] = ic
        st = evaluate.ic_stats(ic)
        ic_rows.append({"factor": name, **st})

        lay = evaluate.layer_returns(p, fwd, ind_eval, n=config.N_LAYERS)
        ls = evaluate.long_short(lay)
        p_top, p_ls = evaluate.perf_stats(lay[0]), evaluate.perf_stats(ls)
        mean_by_layer = lay.mean()
        mono = -mean_by_layer.corr(
            pd.Series(range(len(mean_by_layer)), index=mean_by_layer.index),
            method="spearman")
        layer_rows.append({
            "factor": name,
            "top_ann": p_top.get("ann_return"),
            "top_sharpe": p_top.get("sharpe"),
            "top_maxdd": p_top.get("max_drawdown"),
            "ls_ann": p_ls.get("ann_return"),
            "ls_sharpe": p_ls.get("sharpe"),
            "ls_maxdd": p_ls.get("max_drawdown"),
            "ls_win": p_ls.get("win_rate"),
            "monotonicity": mono,
            "months": len(lay),
        })
        log(f"  {name:12s} IC={st.get('mean', float('nan')):+.4f} "
            f"IR={st.get('ir', float('nan')):+.3f} "
            f"多空年化={p_ls.get('ann_return', float('nan')):+.1%}", lines)

    ic_tbl = pd.DataFrame(ic_rows)
    ic_tbl.to_csv(out_t / "ic_summary.csv", index=False, encoding="utf-8-sig")

    pd.DataFrame(ic_all).to_csv(out_t / "ic_series.csv", encoding="utf-8-sig",
                                index_label="date")

    lay_tbl = pd.DataFrame(layer_rows)
    lay_tbl.to_csv(out_t / "layer_summary.csv", index=False, encoding="utf-8-sig")

    elapsed = time.time() - t0
    log(f"\n完成：{len(config.FACTORS)} 因子，耗时 {elapsed:.1f}s", lines)

    logdir = config.OUT_DIR / "logs"
    logdir.mkdir(parents=True, exist_ok=True)
    (logdir / f"run_{now:%Y%m%d_%H%M%S}_p1_factor_panel.md").write_text(
        "\n".join(lines), encoding="utf-8")

    try:
        import psutil
        import os
        peak = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
        print(f"峰值内存: {peak:.0f} MB")
    except Exception:
        pass


if __name__ == "__main__":
    main()
