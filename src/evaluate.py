"""因子检验：前瞻收益、IC、分层回测、绩效指标。"""

from __future__ import annotations

import numpy as np
import pandas as pd


def forward_return(close: pd.DataFrame, periods: int = 1) -> pd.DataFrame:
    """T 期到 T+periods 期的收益率（对齐到 T 期）。"""
    return close.pct_change(periods).shift(-periods)


def ic_series(factor: pd.DataFrame, fwd_ret: pd.DataFrame,
              method: str = "spearman", min_n: int = 30) -> pd.Series:
    """逐月截面 IC。"""
    out = {}
    for d in factor.index:
        f = factor.loc[d]
        r = fwd_ret.loc[d] if d in fwd_ret.index else None
        if r is None:
            continue
        m = f.notna() & r.notna()
        if m.sum() < min_n:
            continue
        out[d] = f[m].corr(r[m], method=method)
    return pd.Series(out, name="IC").sort_index()


def ic_stats(ic: pd.Series) -> dict:
    ic = ic.dropna()
    if ic.empty:
        return {"n": 0}
    mean, std = ic.mean(), ic.std()
    return {
        "n": int(len(ic)),
        "mean": float(mean),
        "std": float(std),
        "ir": float(mean / std) if std else np.nan,
        "positive_ratio": float((ic > 0).mean()),
        "abs_gt_002": float((ic.abs() > 0.02).mean()),
    }


def assign_layers(factor: pd.DataFrame, industry: pd.DataFrame | None = None,
                  n: int = 5) -> pd.DataFrame:
    """按截面（可选行业内）排序打分，返回 layer 宽表（0=最高分组）。"""
    rows = {}
    for d in factor.index:
        f = factor.loc[d]
        if industry is not None and d in industry.index:
            grp = industry.loc[d].reindex(f.index)
        else:
            grp = pd.Series("all", index=f.index)

        m = f.notna()
        if m.sum() < n:
            continue
        groups = grp[m].fillna("NA")
        pct = f[m].groupby(groups).rank(pct=True, method="first")
        layer = np.minimum((pct * n).astype(int), n - 1)

        s = pd.Series(np.nan, index=f.index)
        s.loc[m] = layer.values
        rows[d] = s
    return pd.DataFrame(rows).T.sort_index()


def layer_returns(factor: pd.DataFrame, fwd_ret: pd.DataFrame,
                  industry: pd.DataFrame | None = None,
                  n: int = 5) -> pd.DataFrame:
    """分层组合的等权月度收益，返回 index=date, columns=layer。"""
    layers = assign_layers(factor, industry, n=n)
    out = {}
    for d in layers.index:
        if d not in fwd_ret.index:
            continue
        lay = layers.loc[d]
        r = fwd_ret.loc[d]
        m = lay.notna() & r.notna()
        if m.sum() == 0:
            continue
        out[d] = r[m].groupby(lay[m]).mean()
    res = pd.DataFrame(out).T.sort_index()
    return res.reindex(columns=range(n))


def long_short(layer_ret: pd.DataFrame, top: int = 0, bottom: int | None = None) -> pd.Series:
    """多空组合收益 = 最高层 - 最低层。"""
    if bottom is None:
        bottom = layer_ret.shape[1] - 1
    return layer_ret[top] - layer_ret[bottom]


def perf_stats(returns: pd.Series, rf: float = 0.0, freq: int = 12) -> dict:
    """年化收益、波动、夏普、最大回撤、胜率。"""
    r = returns.dropna()
    if r.empty:
        return {}
    nav = (1 + r).cumprod()
    ann_ret = nav.iloc[-1] ** (freq / len(r)) - 1
    ann_vol = r.std() * np.sqrt(freq)
    sharpe = (r.mean() * freq - rf) / ann_vol if ann_vol else np.nan
    drawdown = nav / nav.cummax() - 1
    return {
        "ann_return": float(ann_ret),
        "ann_vol": float(ann_vol),
        "sharpe": float(sharpe),
        "max_drawdown": float(drawdown.min()),
        "win_rate": float((r > 0).mean()),
        "n_months": int(len(r)),
    }
