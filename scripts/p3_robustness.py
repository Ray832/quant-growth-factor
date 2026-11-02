# -*- coding: utf-8 -*-
"""P3：稳健性补充（基准超额 / 真实换手与成本 / FDR / 填 0 对照 / 分时段）。

输出：
    output/tables/benchmark_excess.csv   TOP 组合相对沪深300 的超额
    output/tables/turnover_cost.csv      真实换手率与扣费后多空
    output/tables/fdr_summary.csv        IC t 值的 BH-FDR 校正
    output/tables/fill0_compare.csv      缺失剔除 vs 填 0
    output/tables/subperiod_ic.csv       2020–2022 vs 2023–2025

用法：
    & 'E:\\量化研报复现\\env.cmd' scripts\\p3_robustness.py
"""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import config, data, evaluate, factors, preprocess  # noqa: E402

LOG = []
COST = 0.003  # 双边千三


def log(msg):
    print(msg)
    LOG.append(str(msg))


def residualize(f, ind, logmv):
    out = {}
    for d in f.index:
        s, i, m = f.loc[d], ind.loc[d], logmv.loc[d]
        mask = s.notna() & i.notna() & m.notna()
        if mask.sum() < 50:
            continue
        X = pd.get_dummies(i[mask], drop_first=True).astype(float)
        X.insert(0, "const", 1.0)
        X["logmv"] = m[mask].to_numpy()
        y = s[mask].to_numpy()
        beta, *_ = np.linalg.lstsq(X.to_numpy(), y, rcond=None)
        out[d] = pd.Series(y - X.to_numpy() @ beta, index=s[mask].index)
    return pd.DataFrame(out).T.reindex(index=f.index, columns=f.columns)


def prep_neutral(f, ind, logmv):
    x = preprocess.zscore(preprocess.mad_winsorize(f, k=config.MAD_K))
    return residualize(x, ind, logmv)


def bh_fdr(p):
    p = np.asarray(p, dtype=float)
    m = len(p)
    order = np.argsort(p)
    ranked = p[order]
    adj = ranked * m / np.arange(1, m + 1)
    adj = np.minimum.accumulate(adj[::-1])[::-1]
    out = np.empty(m)
    out[order] = np.clip(adj, 0, 1)
    return out


def main():
    t0 = time.time()
    now = datetime.now()
    log(f"# P3 稳健性补充 {now:%Y-%m-%d %H:%M:%S}")

    raw = data.load_panel()
    pool = data.filter_pool(raw)
    wide = data.to_wide(pool)
    ind_all = wide["sw2021_level1_name"]
    close, mv = wide["close"], wide["float_market_cap"]

    start, end = pd.Timestamp(config.EVAL_START), pd.Timestamp(config.EVAL_END)
    dates = [d for d in close.index if start <= d <= end]
    ind, mv, close = ind_all.loc[dates], mv.loc[dates], close.loc[dates]
    logmv = np.log(mv.where(mv > 0))
    fwd = evaluate.forward_return(close)
    fwd = fwd.loc[dates]

    # 基准：沪深300 月收益
    idx = data.load_index("000300").set_index("date")["close"]
    bench = idx.pct_change().reindex(pd.DatetimeIndex(dates))
    bench_ann = (1 + bench.mean()) ** 12 - 1
    log(f"基准沪深300 年化 {bench_ann:.1%}，{bench.notna().sum()} 个月")

    fac_raw = factors.build_factors(wide)

    bench_rows, turn_rows, fdr_rows, fill0_rows, sub_rows = [], [], [], [], []
    ic_tvals, ic_ps = [], []

    mid = pd.Timestamp("2023-01-01")

    for name in config.FACTORS:
        f = fac_raw[name].loc[dates]
        f_neu = prep_neutral(f, ind, logmv)

        # --- 基准超额（5 层 TOP） ---
        lay = evaluate.layer_returns(f_neu, fwd, ind, n=5)
        top = lay[0]
        excess = (top - bench).dropna()
        p_ex = evaluate.perf_stats(excess)
        bench_rows.append({
            "factor": name, "top_ann": p_ex.get("ann_return", np.nan) + bench_ann,
            "bench_ann": bench_ann,
            "excess_ann": p_ex.get("ann_return"),
            "excess_ir": (excess.mean() / excess.std() * np.sqrt(12)) if excess.std() else np.nan,
            "excess_win": (excess > 0).mean(),
            "excess_maxdd": (excess.cumsum() - excess.cumsum().cummax()).min(),
        })

        # --- 真实换手与成本（5 层多空，逐层换手） ---
        layers = evaluate.assign_layers(f_neu, ind, n=5)
        hold = {d: set(layers.columns[layers.loc[d] == 0]) for d in layers.index}
        ds = sorted(hold)
        to = []
        for a, b in zip(ds[:-1], ds[1:]):
            if hold[a]:
                to.append(1 - len(hold[a] & hold[b]) / len(hold[a]))
        avg_to = float(np.mean(to)) if to else np.nan
        ls = evaluate.long_short(lay)
        net = ls - avg_to * COST
        p_gross, p_net = evaluate.perf_stats(ls), evaluate.perf_stats(net)
        turn_rows.append({
            "factor": name, "avg_turnover": avg_to,
            "ls_gross": p_gross.get("ann_return"), "ls_net": p_net.get("ann_return"),
            "sharpe_gross": p_gross.get("sharpe"), "sharpe_net": p_net.get("sharpe"),
            "cost_drag_ann": (p_gross.get("ann_return") or 0) - (p_net.get("ann_return") or 0),
        })

        # --- IC 与 FDR ---
        ic = evaluate.ic_series(f_neu, fwd)
        n = len(ic)
        tval = ic.mean() / ic.std() * np.sqrt(n)
        pval = 2 * (1 - norm.cdf(abs(tval)))
        ic_tvals.append(tval)
        ic_ps.append(pval)
        fdr_rows.append({"factor": name, "ic_mean": ic.mean(), "t": tval, "p": pval})

        # --- 填 0 对照 ---
        ic_raw = evaluate.ic_series(f_neu, fwd)
        ic_fill = evaluate.ic_series(f_neu.fillna(0), fwd)
        fill0_rows.append({
            "factor": name, "ic_drop": ic_raw.mean(), "ic_fill0": ic_fill.mean(),
            "diff": ic_fill.mean() - ic_raw.mean(),
        })

        # --- 分时段 ---
        early = ic[ic.index < mid]
        late = ic[ic.index >= mid]
        sub_rows.append({
            "factor": name, "ic_2020_2022": early.mean(), "ic_2023_2025": late.mean(),
            "n_early": len(early), "n_late": len(late),
        })

        log(f"  {name:12s} 换手={avg_to:.1%} 超额={p_ex.get('ann_return', float('nan')):+.1%} "
            f"IC早={early.mean():+.4f} 晚={late.mean():+.4f}")

    pd.DataFrame(bench_rows).to_csv(config.OUT_DIR / "tables/benchmark_excess.csv",
                                    index=False, encoding="utf-8-sig")
    pd.DataFrame(turn_rows).to_csv(config.OUT_DIR / "tables/turnover_cost.csv",
                                   index=False, encoding="utf-8-sig")
    pd.DataFrame(fill0_rows).to_csv(config.OUT_DIR / "tables/fill0_compare.csv",
                                    index=False, encoding="utf-8-sig")
    pd.DataFrame(sub_rows).to_csv(config.OUT_DIR / "tables/subperiod_ic.csv",
                                  index=False, encoding="utf-8-sig")

    fdr = pd.DataFrame(fdr_rows)
    fdr["p_adj"] = bh_fdr(fdr["p"])
    fdr["sig_5pct"] = fdr["p_adj"] < 0.05
    fdr.to_csv(config.OUT_DIR / "tables/fdr_summary.csv", index=False, encoding="utf-8-sig")

    log(f"\n完成，耗时 {time.time() - t0:.1f}s")
    (config.OUT_DIR / "logs").mkdir(parents=True, exist_ok=True)
    (config.OUT_DIR / "logs" / f"run_{now:%Y%m%d_%H%M%S}_p3_robustness.md").write_text(
        "\n".join(LOG), encoding="utf-8")


if __name__ == "__main__":
    main()
