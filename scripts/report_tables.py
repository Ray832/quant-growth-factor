# -*- coding: utf-8 -*-
"""生成研报统一口径的 5 层结果表（行业+市值中性、真实换手成本）。"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import config, data, evaluate, factors, preprocess  # noqa: E402

COST = 0.003


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
        b, *_ = np.linalg.lstsq(X.to_numpy(), y, rcond=None)
        out[d] = pd.Series(y - X.to_numpy() @ b, index=s[mask].index)
    return pd.DataFrame(out).T.reindex(index=f.index, columns=f.columns)


def main():
    raw = data.load_panel()
    pool = data.apply_next_day_suspension(data.filter_pool(raw))
    wide = data.to_wide(pool)
    close = wide["close"]
    dates = [d for d in close.index
             if pd.Timestamp(config.EVAL_START) <= d <= pd.Timestamp(config.EVAL_END)]
    close, ind = close.loc[dates], wide["sw2021_level1_name"].loc[dates]
    mv = wide["float_market_cap"].loc[dates]
    logmv = np.log(mv.where(mv > 0))
    fwd = evaluate.forward_return(close)

    rows = []
    for name, f in factors.build_factors(wide).items():
        f = f.loc[dates]
        x = preprocess.zscore(preprocess.mad_winsorize(f, k=config.MAD_K))
        fn = residualize(x, ind, logmv)

        lay = evaluate.layer_returns(fn, fwd, ind, n=5)
        ls = lay[0] - lay[4]

        layers = evaluate.assign_layers(fn, ind, n=5)
        hold = {d: set(layers.columns[layers.loc[d] == 0]) for d in layers.index}
        ds = sorted(hold)
        to = [1 - len(hold[a] & hold[b]) / len(hold[a])
              for a, b in zip(ds[:-1], ds[1:]) if hold[a]]
        avg_to = float(np.mean(to)) if to else np.nan

        net = ls - avg_to * COST
        p_top = evaluate.perf_stats(lay[0])
        p_g = evaluate.perf_stats(ls)
        p_n = evaluate.perf_stats(net)
        mean_l = lay.mean()
        mono = -mean_l.corr(pd.Series(range(5), index=mean_l.index), method="spearman")

        rows.append({
            "factor": name,
            "top_ann": p_top.get("ann_return"),
            "ls_gross": p_g.get("ann_return"),
            "ls_net": p_n.get("ann_return"),
            "ls_sharpe": p_g.get("sharpe"),
            "ls_sharpe_net": p_n.get("sharpe"),
            "ls_maxdd": p_g.get("max_drawdown"),
            "turnover": avg_to,
            "monotonicity": mono,
        })
        print(name, "ok")

    pd.DataFrame(rows).to_csv(config.OUT_DIR / "tables" / "report_layer.csv",
                              index=False, encoding="utf-8-sig")
    print("saved report_layer.csv")


if __name__ == "__main__":
    main()
