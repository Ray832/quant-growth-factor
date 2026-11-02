# -*- coding: utf-8 -*-
"""P2：全样本检验（回归法 / IC 衰减 / 10 层 / 分市值 / 分行业 / 成本）。

全部基于全样本（5,317 只、72 个月），不使用冒烟测试的小样本。

输出：
    output/tables/regression_summary.csv   回归法汇总（对应原文表 32）
    output/tables/regression_series.csv    因子收益率与 t 值序列
    output/tables/ic_decay.csv             IC 衰减（t+1 ~ t+6）
    output/tables/layer10_summary.csv      10 层回测汇总
    output/tables/size_ic_summary.csv      分市值 IC
    output/tables/industry_ic_summary.csv  分行业 IC
    output/tables/cost_summary.csv         扣费前后多空收益

用法：
    & 'E:\\量化研报复现\\env.cmd' scripts\\full_sample_tests.py
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

LOG = []


def log(msg):
    print(msg)
    LOG.append(str(msg))


def prep_raw(f):
    """去极值 + 标准化，不做行业中性（回归法用）。"""
    return preprocess.zscore(preprocess.mad_winsorize(f, k=config.MAD_K))


def residualize(f, ind, logmv):
    """按截面对行业哑变量 + ln(流通市值) 回归取残差（IC 用）。"""
    out = {}
    for d in f.index:
        s, i, m = f.loc[d], ind.loc[d], logmv.loc[d]
        mask = s.notna() & i.notna() & m.notna()
        if mask.sum() < 50:
            continue
        X = pd.get_dummies(i[mask], drop_first=True).astype(float)
        X.insert(0, "const", 1.0)
        X["logmv"] = m[mask].values
        y = s[mask].to_numpy()
        beta, *_ = np.linalg.lstsq(X.to_numpy(), y, rcond=None)
        out[d] = pd.Series(y - X.to_numpy() @ beta, index=s[mask].index)
    return pd.DataFrame(out).T.reindex(index=f.index, columns=f.columns)


def prep_neutral(f, ind, logmv):
    return residualize(preprocess.zscore(preprocess.mad_winsorize(f, k=config.MAD_K)), ind, logmv)


def wls_month(y, f, ind, w):
    """行业哑变量 + 单因子的加权最小二乘（FWL 等价实现），返回 (beta, t)。"""
    m = y.notna() & f.notna() & ind.notna() & w.notna()
    if m.sum() < 50:
        return np.nan, np.nan
    d = pd.DataFrame({"y": y[m], "f": f[m], "ind": ind[m], "w": w[m]})
    d["wy"] = d["y"] * d["w"]
    d["wf"] = d["f"] * d["w"]
    g = d.groupby("ind")[["w", "wy", "wf"]].sum()
    g["ybar"] = g["wy"] / g["w"]
    g["fbar"] = g["wf"] / g["w"]
    d = d.join(g[["ybar", "fbar"]], on="ind")
    yr = d["y"] - d["ybar"]
    fr = d["f"] - d["fbar"]
    denom = (d["w"] * fr ** 2).sum()
    if denom <= 0:
        return np.nan, np.nan
    beta = (d["w"] * yr * fr).sum() / denom
    e = yr - beta * fr
    k = d["ind"].nunique() + 1
    sigma2 = (d["w"] * e ** 2).sum() / max(len(d) - k, 1)
    se = np.sqrt(sigma2 / denom)
    return beta, beta / se if se > 0 else np.nan


def main():
    t0 = time.time()
    now = datetime.now()
    log(f"# P2 全样本检验 {now:%Y-%m-%d %H:%M:%S}")

    raw = data.load_panel()
    pool = data.filter_pool(raw)
    wide = data.to_wide(pool)
    ind = wide["sw2021_level1_name"]
    close, mv = wide["close"], wide["float_market_cap"]
    log(f"样本：{len(pool):,d} 行 / {pool['instrument'].nunique():,d} 只")

    start, end = pd.Timestamp(config.EVAL_START), pd.Timestamp(config.EVAL_END)
    dates = [d for d in close.index if start <= d <= end]
    ind, mv, close = ind.loc[dates], mv.loc[dates], close.loc[dates]
    logmv = np.log(mv.where(mv > 0))

    fac_raw = factors.build_factors(wide)
    fwd1 = close.pct_change(1).shift(-1).loc[dates]

    out_t = config.OUT_DIR / "tables"
    out_t.mkdir(parents=True, exist_ok=True)

    reg_rows, reg_series = [], {}
    ic_decay_rows = []
    layer10_rows, size_rows, cost_rows = [], [], []
    ind_ic_all = {}

    horizons = {h: close.pct_change(h).shift(-h).loc[dates] for h in range(1, 7)}

    for name in config.FACTORS:
        f_raw = fac_raw[name].loc[dates]
        f_reg = prep_raw(f_raw)
        f_neu = prep_neutral(f_raw, ind, logmv)

        # --- 回归法 ---
        betas, ts = {}, {}
        for d in dates:
            b, t = wls_month(fwd1.loc[d], f_reg.loc[d], ind.loc[d], np.sqrt(mv.loc[d]))
            betas[d], ts[d] = b, t
        beta_s = pd.Series(betas).dropna()
        t_s = pd.Series(ts).dropna()
        reg_series[name] = {"beta": beta_s, "t": t_s}
        reg_rows.append({
            "factor": name,
            "abs_t_mean": t_s.abs().mean(),
            "pct_abs_t_gt2": (t_s.abs() > 2).mean(),
            "t_mean_over_std": t_s.mean() / t_s.std(),
            "beta_mean": beta_s.mean(),
            "beta_t_stat": beta_s.mean() / beta_s.std() * np.sqrt(len(beta_s)),
            "months": len(beta_s),
        })

        # --- IC 衰减 ---
        row = {"factor": name}
        for h in range(1, 7):
            ic = evaluate.ic_series(f_neu, horizons[h])
            row[f"IC_t{h}"] = ic.mean()
        ic_decay_rows.append(row)

        # --- 10 层 ---
        lay = evaluate.layer_returns(f_neu, fwd1, ind, n=10)
        if lay.notna().any().any():
            ls = lay[0] - lay[9]
            p_top, p_ls = evaluate.perf_stats(lay[0]), evaluate.perf_stats(ls)
            mean_by_layer = lay.mean()
            mono = -mean_by_layer.corr(
                pd.Series(range(len(mean_by_layer)), index=mean_by_layer.index),
                method="spearman")
            layer10_rows.append({
                "factor": name, "top_ann": p_top.get("ann_return"),
                "ls_ann": p_ls.get("ann_return"), "ls_sharpe": p_ls.get("sharpe"),
                "ls_maxdd": p_ls.get("max_drawdown"), "monotonicity": mono,
            })

            # --- 成本 ---
            net = ls - 0.003
            p_net = evaluate.perf_stats(net)
            cost_rows.append({
                "factor": name, "ls_gross": p_ls.get("ann_return"),
                "ls_net": p_net.get("ann_return"),
                "sharpe_gross": p_ls.get("sharpe"), "sharpe_net": p_net.get("sharpe"),
            })

        # --- 分市值 IC ---
        for grp, label in ((0, "small"), (1, "mid"), (2, "large")):
            ics = {}
            for d in dates:
                s = mv.loc[d]
                if s.notna().sum() < 100:
                    continue
                q = pd.qcut(s.rank(method="first"), 3, labels=[0, 1, 2])
                mask = (q == grp)
                fsub = f_neu.loc[d][mask.reindex(f_neu.columns).fillna(False).values]
                ysub = fwd1.loc[d][mask.reindex(fwd1.columns).fillna(False).values]
                m = fsub.notna() & ysub.notna()
                if m.sum() >= 30:
                    ics[d] = fsub[m].corr(ysub[m], method="spearman")
            size_rows.append({"factor": name, "size": label,
                              "ic_mean": pd.Series(ics).mean(),
                              "ic_std": pd.Series(ics).std()})

        # --- 分行业 IC ---
        per_ind = {}
        for d in dates:
            f_s, y_s, i_s = f_neu.loc[d], fwd1.loc[d], ind.loc[d]
            for k, idx in i_s.groupby(i_s).groups.items():
                fs, ys = f_s.reindex(idx), y_s.reindex(idx)
                m = fs.notna() & ys.notna()
                if m.sum() >= 10:
                    per_ind.setdefault(k, []).append(fs[m].corr(ys[m], method="spearman"))
        ind_ic_all[name] = {k: np.nanmean(v) for k, v in per_ind.items()}

        log(f"  {name:12s} |t|={reg_rows[-1]['abs_t_mean']:.2f} "
            f"beta_t={reg_rows[-1]['beta_t_stat']:+.2f} "
            f"IC1={ic_decay_rows[-1]['IC_t1']:+.4f} IC6={ic_decay_rows[-1]['IC_t6']:+.4f}")

    pd.DataFrame(reg_rows).to_csv(out_t / "regression_summary.csv", index=False, encoding="utf-8-sig")

    reg_out = {}
    for name, d in reg_series.items():
        reg_out[f"{name}_beta"] = d["beta"]
        reg_out[f"{name}_t"] = d["t"]
    pd.DataFrame(reg_out).to_csv(out_t / "regression_series.csv", encoding="utf-8-sig", index_label="date")

    pd.DataFrame(ic_decay_rows).to_csv(out_t / "ic_decay.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(layer10_rows).to_csv(out_t / "layer10_summary.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(size_rows).to_csv(out_t / "size_ic_summary.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(cost_rows).to_csv(out_t / "cost_summary.csv", index=False, encoding="utf-8-sig")

    ind_tbl = pd.DataFrame(ind_ic_all).T
    ind_tbl.index.name = "industry"
    ind_tbl.reset_index().to_csv(out_t / "industry_ic_summary.csv", index=False, encoding="utf-8-sig")

    log(f"\n完成，耗时 {time.time() - t0:.1f}s")

    logdir = config.OUT_DIR / "logs"
    logdir.mkdir(parents=True, exist_ok=True)
    (logdir / f"run_{now:%Y%m%d_%H%M%S}_p2_full_tests.md").write_text("\n".join(LOG), encoding="utf-8")


if __name__ == "__main__":
    main()
