#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
成长因子单因子测试 · BigQuant 平台单文件版
================================================

把整个流水线压进一个文件：读数据 → 12 因子 → 预处理 → IC / 分层 / 回归 / FDR → 图表。
可直接拷到 BigQuant 的 web VSCode 里运行，不需要 `src/` 包。

数据源
------
1) local（默认）：读 `bq_export_v41/panel_*.csv`、`suspension_events.csv`
   - 适合平台上已上传数据文件的情况
2) dai：直接查平台 `cn_stock_prefactors`
   - 适合平台上没有 CSV、想现取的情况

用法
----
# 平台已有数据文件（推荐先试这个）
python bq_factor_lab.py --source local --data-dir ./bq_export_v41 --out-dir ./out

# 从平台现取
python bq_factor_lab.py --source dai --start 2020-01-01 --end 2025-12-31

# 小样本快速验证（100 只股票）
python bq_factor_lab.py --source local --data-dir ./bq_export_v41 --sample 100

输出
----
out/ic_summary.csv         IC 汇总
out/ic_series.csv          IC 时间序列
out/layer_summary.csv      5 层回测
out/regression_summary.csv 回归法（WLS）
out/fdr_summary.csv        BH-FDR 校正
out/ls_nav.png             多空净值图
"""

from __future__ import annotations

import argparse
import os
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

FACTORS = [
    "Sales_G_q", "Sales_G_ttm", "Sales_G_3y",
    "Profit_G_q", "Profit_G_ttm", "Profit_G_3y",
    "OCF_G_q", "OCF_G_ttm", "OCF_G_3y",
    "ROE_G_q", "ROE_G_ttm", "ROE_G_3y",
]

PANEL_COLS = [
    "date", "instrument", "close", "float_market_cap",
    "st_status", "suspended", "list_days", "is_bj", "sw2021_level1_name",
    "operating_revenue_mrq", "operating_revenue_ttm",
    "net_profit_mrq", "net_profit_ttm",
    "net_cffoa_mrq", "net_cffoa_ttm",
    "total_equity_to_parent_shareholders",
]

MIN_LIST_DAYS = 365
MAD_K = 5.0
N_LAYERS = 5


# ---------------------------------------------------------------------------
# 数据读取
# ---------------------------------------------------------------------------

def load_local(data_dir: str, years=None) -> pd.DataFrame:
    files = sorted(Path(data_dir).glob("panel_*.csv"))
    if years is not None:
        files = [f for f in files if int(f.stem.split("_")[1]) in set(years)]
    if not files:
        raise FileNotFoundError(f"{data_dir} 下没有 panel_*.csv")
    cols = [c for c in PANEL_COLS]
    frames = [pd.read_csv(f, usecols=cols, parse_dates=["date"]) for f in files]
    return pd.concat(frames, ignore_index=True)


def load_dai(start: str, end: str) -> pd.DataFrame:
    import dai
    sql = f"""
    SELECT {', '.join(PANEL_COLS)}
    FROM cn_stock_prefactors
    WHERE date >= '{start}' AND date <= '{end}'
    """
    return dai.query(sql, filters={"date": [start, end]}).df()


def load_suspension(data_dir: str) -> pd.DataFrame:
    p = Path(data_dir) / "suspension_events.csv"
    if not p.exists():
        return pd.DataFrame(columns=["date", "instrument"])
    return pd.read_csv(p, parse_dates=["date"])


def filter_pool(df: pd.DataFrame, min_list_days: int = MIN_LIST_DAYS) -> pd.DataFrame:
    mask = (
        df["is_bj"].fillna(0).eq(0)
        & df["st_status"].fillna(0).le(0)
        & df["suspended"].fillna(0).eq(0)
        & (df["list_days"].fillna(0) >= min_list_days)
    )
    return df[mask].copy()


def exclude_next_day_suspension(pool: pd.DataFrame, susp: pd.DataFrame,
                                max_gap_days: int = 5) -> pd.DataFrame:
    """剔除"截面期下一交易日停牌"的股票。"""
    if susp.empty:
        return pool
    by_date = susp.groupby("date")["instrument"].apply(set).to_dict()
    cal = pd.DatetimeIndex(sorted(set(susp["date"]) | set(pool["date"])))
    drop = set()
    for d in pd.DatetimeIndex(sorted(pool["date"].unique())):
        later = cal[cal > d]
        if len(later) == 0:
            continue
        nd = later[0]
        if (nd - d).days > max_gap_days:
            continue
        for inst in by_date.get(nd, ()):
            drop.add((d, inst))
    if not drop:
        return pool
    keys = pd.Series(list(zip(pool["date"], pool["instrument"])), index=pool.index)
    return pool[~keys.isin(drop)]


def to_wide(df: pd.DataFrame) -> dict:
    cols = [c for c in df.columns if c not in ("date", "instrument")]
    return {c: df.pivot(index="date", columns="instrument", values=c).sort_index()
            for c in cols}


# ---------------------------------------------------------------------------
# 因子
# ---------------------------------------------------------------------------

def _growth(cur, base):
    den = base.abs()
    return ((cur - base) / den.where(den > 1e-9)).replace([np.inf, -np.inf], np.nan)


def _cagr(cur, base, years=3):
    ratio = (cur / base.where(base > 0)).where(cur > 0)
    return (ratio.pow(1.0 / years) - 1.0).replace([np.inf, -np.inf], np.nan)


def _roe(profit, equity):
    return (profit / equity.where(equity > 0)).replace([np.inf, -np.inf], np.nan)


def sanitize(w: dict) -> dict:
    """0 填充、负营收统一视为缺失。"""
    out = dict(w)
    for c in ("operating_revenue_mrq", "operating_revenue_ttm"):
        out[c] = w[c].where(w[c] > 0)
    for c in ("net_profit_mrq", "net_profit_ttm", "net_cffoa_mrq", "net_cffoa_ttm"):
        out[c] = w[c].replace(0.0, np.nan)
    eq = "total_equity_to_parent_shareholders"
    out[eq] = w[eq].where(w[eq] > 0)
    return out


def build_factors(w: dict) -> dict:
    w = sanitize(w)
    out = {}
    for prefix, q, ttm in (
        ("Sales", "operating_revenue_mrq", "operating_revenue_ttm"),
        ("Profit", "net_profit_mrq", "net_profit_ttm"),
        ("OCF", "net_cffoa_mrq", "net_cffoa_ttm"),
    ):
        out[f"{prefix}_G_q"] = _growth(w[q], w[q].shift(12))
        out[f"{prefix}_G_ttm"] = _growth(w[ttm], w[ttm].shift(12))
        out[f"{prefix}_G_3y"] = _cagr(w[ttm], w[ttm].shift(36))

    roe_q = _roe(w["net_profit_mrq"], w["total_equity_to_parent_shareholders"])
    roe_t = _roe(w["net_profit_ttm"], w["total_equity_to_parent_shareholders"])
    out["ROE_G_q"] = _growth(roe_q, roe_q.shift(12))
    out["ROE_G_ttm"] = _growth(roe_t, roe_t.shift(12))
    out["ROE_G_3y"] = _cagr(roe_t, roe_t.shift(36))
    return {k: out[k] for k in FACTORS}


# ---------------------------------------------------------------------------
# 预处理与检验
# ---------------------------------------------------------------------------

def mad_winsorize(df, k=MAD_K):
    med = df.median(axis=1)
    mad = df.sub(med, axis=0).abs().median(axis=1)
    return df.clip(lower=med - k * mad, upper=med + k * mad, axis=0)


def zscore(df):
    std = df.std(axis=1).replace(0, np.nan)
    return df.sub(df.mean(axis=1), axis=0).div(std, axis=0)


def residualize(f, ind, logmv):
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
        b, *_ = np.linalg.lstsq(X.to_numpy(), y, rcond=None)
        out[d] = pd.Series(y - X.to_numpy() @ b, index=s[mask].index)
    return pd.DataFrame(out).T.reindex(index=f.index, columns=f.columns)


def prep(f, ind=None, logmv=None):
    x = zscore(mad_winsorize(f))
    if ind is not None and logmv is not None:
        x = residualize(x, ind, logmv)
    return x


def forward_return(close, periods=1):
    return close.pct_change(periods).shift(-periods)


def ic_series(factor, fwd, min_n=30):
    out = {}
    for d in factor.index:
        if d not in fwd.index:
            continue
        f, r = factor.loc[d], fwd.loc[d]
        m = f.notna() & r.notna()
        if m.sum() >= min_n:
            out[d] = f[m].corr(r[m], method="spearman")
    return pd.Series(out).sort_index()


def ic_stats(ic):
    if len(ic) == 0:
        return {}
    m, s = ic.mean(), ic.std()
    return {"n": len(ic), "mean": m, "std": s, "ir": m / s if s else np.nan,
            "t": m / s * np.sqrt(len(ic)) if s else np.nan,
            "positive_ratio": (ic > 0).mean()}


def assign_layers(factor, ind=None, n=N_LAYERS):
    rows = {}
    for d in factor.index:
        f = factor.loc[d]
        grp = ind.loc[d].reindex(f.index) if ind is not None else pd.Series("all", index=f.index)
        m = f.notna()
        if m.sum() < n:
            continue
        pct = f[m].groupby(grp[m].fillna("NA")).rank(pct=True, method="first")
        layer = (n - 1) - np.minimum((pct * n).astype(int), n - 1)
        s = pd.Series(np.nan, index=f.index)
        s.loc[m] = layer.values
        rows[d] = s
    return pd.DataFrame(rows).T.sort_index()


def layer_returns(factor, fwd, ind=None, n=N_LAYERS):
    layers = assign_layers(factor, ind, n)
    out = {}
    for d in layers.index:
        if d not in fwd.index:
            continue
        lay, r = layers.loc[d], fwd.loc[d]
        m = lay.notna() & r.notna()
        if m.sum():
            out[d] = r[m].groupby(lay[m]).mean()
    return pd.DataFrame(out).T.sort_index().reindex(columns=range(n))


def perf_stats(r):
    r = r.dropna()
    if r.empty:
        return {}
    nav = (1 + r).cumprod()
    ann = nav.iloc[-1] ** (12 / len(r)) - 1
    vol = r.std() * np.sqrt(12)
    return {"ann_return": ann, "ann_vol": vol,
            "sharpe": ann / vol if vol else np.nan,
            "max_drawdown": (nav / nav.cummax() - 1).min(),
            "win_rate": (r > 0).mean(), "n": len(r)}


def wls_month(y, f, ind, w):
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
    yr, fr = d["y"] - d["ybar"], d["f"] - d["fbar"]
    denom = (d["w"] * fr ** 2).sum()
    if denom <= 0:
        return np.nan, np.nan
    beta = (d["w"] * yr * fr).sum() / denom
    e = yr - beta * fr
    k = d["ind"].nunique() + 1
    sigma2 = (d["w"] * e ** 2).sum() / max(len(d) - k, 1)
    se = np.sqrt(sigma2 / denom)
    return beta, beta / se if se > 0 else np.nan


def bh_fdr(p):
    p = np.asarray(p, float)
    m = len(p)
    order = np.argsort(p)
    adj = p[order] * m / np.arange(1, m + 1)
    adj = np.minimum.accumulate(adj[::-1])[::-1]
    out = np.empty(m)
    out[order] = np.clip(adj, 0, 1)
    return out


# ---------------------------------------------------------------------------
# 绘图
# ---------------------------------------------------------------------------

def setup_font(lang="auto"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    cjk = ["Noto Sans CJK SC", "WenQuanYi Zen Hei", "SimHei", "Microsoft YaHei"]
    available = {f.name for f in font_manager.fontManager.ttflist}
    hit = [f for f in cjk if f in available]
    if lang == "auto":
        lang = "zh" if hit else "en"
    if lang == "zh" and hit:
        plt.rcParams["font.sans-serif"] = [hit[0]]
        plt.rcParams["axes.unicode_minus"] = False
    return plt, lang


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["local", "dai"], default="local")
    ap.add_argument("--data-dir", default="./bq_export_v41")
    ap.add_argument("--out-dir", default="./out")
    ap.add_argument("--start", default="2020-01-01")
    ap.add_argument("--end", default="2025-12-31")
    ap.add_argument("--sample", type=int, default=0, help="只取前 N 只股票（快速验证）")
    ap.add_argument("--lang", choices=["auto", "zh", "en"], default="auto")
    args = ap.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    print(f"[1/6] 读取数据（{args.source}）")
    if args.source == "local":
        raw = load_local(args.data_dir)
        susp = load_suspension(args.data_dir)
    else:
        raw = load_dai(args.start, args.end)
        susp = pd.DataFrame(columns=["date", "instrument"])
    print(f"      原始 {len(raw):,d} 行，{raw['date'].nunique()} 个截面")

    print("[2/6] 过滤股票池")
    pool = filter_pool(raw)
    pool = exclude_next_day_suspension(pool, susp)
    if args.sample:
        keep = (pool.groupby("instrument")["close"].count()
                .sort_values(ascending=False).head(args.sample).index)
        pool = pool[pool["instrument"].isin(keep)]
    print(f"      过滤后 {len(pool):,d} 行，{pool['instrument'].nunique():,d} 只")

    wide = to_wide(pool)
    ind = wide["sw2021_level1_name"]
    close, mv = wide["close"], wide["float_market_cap"]
    dates = [d for d in close.index
             if pd.Timestamp(args.start) <= d <= pd.Timestamp(args.end)]
    ind, mv, close = ind.loc[dates], mv.loc[dates], close.loc[dates]
    logmv = np.log(mv.where(mv > 0))

    print("[3/6] 构建因子")
    fac = build_factors(wide)
    fwd = forward_return(close).loc[dates]

    print("[4/6] IC / 分层 / 回归")
    ic_rows, ic_all, layer_rows, reg_rows = [], {}, [], []
    navs = {}
    for name in FACTORS:
        f = fac[name].loc[dates]
        f_neu = prep(f, ind, logmv)
        f_reg = prep(f)

        ic = ic_series(f_neu, fwd)
        ic_all[name] = ic
        ic_rows.append({"factor": name, **ic_stats(ic)})

        lay = layer_returns(f_neu, fwd, ind)
        p_top, p_ls = perf_stats(lay[0]), perf_stats(lay[0] - lay[lay.columns[-1]])
        mean_l = lay.mean()
        mono = -mean_l.corr(pd.Series(range(len(mean_l)), index=mean_l.index),
                            method="spearman")
        layer_rows.append({"factor": name, "top_ann": p_top.get("ann_return"),
                           "ls_ann": p_ls.get("ann_return"),
                           "ls_sharpe": p_ls.get("sharpe"),
                           "ls_maxdd": p_ls.get("max_drawdown"),
                           "monotonicity": mono})
        if name.endswith("_q"):
            navs[name] = (1 + (lay[0] - lay[lay.columns[-1]])).cumprod()

        betas, ts = [], []
        for d in dates:
            b, t = wls_month(fwd.loc[d], f_reg.loc[d], ind.loc[d], np.sqrt(mv.loc[d]))
            betas.append(b)
            ts.append(t)
        ts = pd.Series(ts).dropna()
        bs = pd.Series(betas).dropna()
        reg_rows.append({"factor": name, "abs_t_mean": ts.abs().mean(),
                         "pct_abs_t_gt2": (ts.abs() > 2).mean(),
                         "beta_mean": bs.mean(),
                         "beta_t": bs.mean() / bs.std() * np.sqrt(len(bs)),
                         "months": len(bs)})
        print(f"      {name:12s} IC={ic.mean():+.4f} 多空={p_ls.get('ann_return', np.nan):+.1%}")

    ic_tbl = pd.DataFrame(ic_rows)
    ic_tbl.to_csv(out / "ic_summary.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(ic_all).to_csv(out / "ic_series.csv", encoding="utf-8-sig", index_label="date")
    pd.DataFrame(layer_rows).to_csv(out / "layer_summary.csv", index=False, encoding="utf-8-sig")
    reg = pd.DataFrame(reg_rows)
    reg.to_csv(out / "regression_summary.csv", index=False, encoding="utf-8-sig")

    fdr = ic_tbl[["factor", "mean", "t"]].copy()
    from math import erf, sqrt as _sqrt

    def _two_sided_p(x):
        if pd.isna(x):
            return np.nan
        return 2 * 0.5 * (1 - erf(abs(x) / _sqrt(2)))

    fdr["p"] = [_two_sided_p(x) for x in fdr["t"]]
    fdr["p_adj"] = bh_fdr(fdr["p"].fillna(1))
    fdr["sig_5pct"] = fdr["p_adj"] < 0.05
    fdr.to_csv(out / "fdr_summary.csv", index=False, encoding="utf-8-sig")

    print("[5/6] 绘图")
    try:
        plt, lang = setup_font(args.lang)
        fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
        for k, v in navs.items():
            ax.plot(v.index, v.values, label=k, lw=1.2)
        ax.axhline(1.0, color="gray", lw=0.8, ls="--")
        ax.set_title("Long-short NAV" if lang == "en" else "多空净值")
        ax.legend(fontsize=7, ncol=2)
        fig.tight_layout()
        fig.savefig(out / "ls_nav.png")
        print(f"      已保存 {out / 'ls_nav.png'}")
    except Exception as e:
        print(f"      绘图跳过：{type(e).__name__}: {e}")

    print("[6/6] 完成")
    print(ic_tbl.round(4).to_string(index=False))
    print(f"\n输出目录: {out.resolve()}")


if __name__ == "__main__":
    main()
