"""端到端冒烟测试：用小样本验证数据、因子、IC、分层是否可用。

运行：
    & 'E:\\量化研报复现\\env.cmd' -m pytest tests -q
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src import config, evaluate


# ---------------------------------------------------------------------------
# 1. 数据层
# ---------------------------------------------------------------------------

def test_panel_integrity(sample):
    raw = sample["raw"]
    assert raw["date"].nunique() >= 110, "月频截面数量不足"
    assert raw.duplicated(["date", "instrument"]).sum() == 0
    assert set(config.PANEL_COLS).issubset(set(raw.columns))


def test_pool_rules(sample):
    pool = sample["pool"]
    assert (pool["is_bj"] == 0).all()
    assert (pool["st_status"] <= 0).all()
    assert (pool["suspended"] == 0).all()
    assert (pool["list_days"] >= config.MIN_LIST_DAYS).all()


# ---------------------------------------------------------------------------
# 2. 因子层
# ---------------------------------------------------------------------------

def test_all_factors_built(sample):
    fac = sample["factors"]
    assert set(fac) == set(config.FACTORS)
    for name, df in fac.items():
        assert df.shape[0] == len(sample["dates"]), f"{name} 日期数不对"
        assert df.notna().sum().sum() > 0, f"{name} 全为空"


def test_factor_coverage(sample):
    """单季/TTM 因子应覆盖大部分股票，三年复合因子覆盖率低一些。"""
    fac = sample["factors"]
    last = sample["dates"][-1]
    for name in ["Sales_G_q", "Profit_G_q", "OCF_G_q", "ROE_G_ttm"]:
        ratio = fac[name].loc[last].notna().mean()
        assert ratio > 0.6, f"{name} 覆盖率过低: {ratio:.2%}"


def test_no_lookahead(sample):
    """截断未来数据，因子值不应改变（防止前视偏差）。"""
    from src import data, factors

    sub = sample["sub"]
    cutoff = pd.Timestamp("2023-12-31")
    truncated = sub[sub["date"] <= cutoff].copy()

    wide_full = data.to_wide(sub)
    wide_trunc = data.to_wide(truncated)

    f_full = factors.build_factors(wide_full)["Sales_G_q"]
    f_trunc = factors.build_factors(wide_trunc)["Sales_G_q"]

    d = f_full.index[f_full.index <= cutoff][-1]
    a = f_full.loc[d].dropna()
    b = f_trunc.loc[d].reindex(a.index)
    pd.testing.assert_series_equal(a, b, check_names=False, rtol=1e-10, atol=1e-12)


def test_winsorize_bounds(sample):
    """去极值后，每行不应超过 median ± 5×MAD。"""
    from src import preprocess

    raw = sample["factors_raw"]["Profit_G_q"]
    win = preprocess.mad_winsorize(raw, k=5)

    med = raw.median(axis=1)
    mad = raw.sub(med, axis=0).abs().median(axis=1)
    upper = (med + 5 * mad).to_numpy()[:, None]
    lower = (med - 5 * mad).to_numpy()[:, None]

    w = win.to_numpy()
    mask = ~np.isnan(w)
    assert (w[mask] <= upper.repeat(w.shape[1], axis=1)[mask] + 1e-9).all()
    assert (w[mask] >= lower.repeat(w.shape[1], axis=1)[mask] - 1e-9).all()


def test_zscore_normalized(sample):
    """标准化后，每个截面均值≈0、标准差≈1。"""
    fac = sample["factors"]["Profit_G_q"]
    rows = fac.dropna(how="all").index
    for d in rows[::20]:
        s = fac.loc[d].dropna()
        if len(s) < 30:
            continue
        assert abs(s.mean()) < 1e-6
        assert abs(s.std() - 1) < 1e-6


# ---------------------------------------------------------------------------
# 3. 检验层
# ---------------------------------------------------------------------------

def test_ic_series(sample):
    ic = evaluate.ic_series(sample["factors"]["Profit_G_q"], sample["fwd"])
    assert len(ic) >= 60
    assert ic.between(-1, 1).all()
    stats = evaluate.ic_stats(ic)
    assert stats["n"] >= 60
    assert abs(stats["mean"]) < 0.3, "IC 均值异常，可能有数据泄露"


def test_layers_and_long_short(sample):
    lay = evaluate.layer_returns(
        sample["factors"]["ROE_G_ttm"], sample["fwd"], sample["industry"], n=5
    )
    assert lay.shape[1] == 5
    assert lay.dropna(how="all").shape[0] >= 60

    ls = evaluate.long_short(lay)
    perf = evaluate.perf_stats(ls)
    assert set(perf) >= {"ann_return", "ann_vol", "sharpe", "max_drawdown"}
    assert np.isfinite(perf["ann_return"])
    assert -1 < perf["max_drawdown"] <= 0


def test_all_factors_produce_ic(sample):
    """12 个因子都能产出 IC 序列，不报错。"""
    for name, f in sample["factors"].items():
        ic = evaluate.ic_series(f, sample["fwd"])
        assert len(ic) >= 30, f"{name} IC 序列过短"


def test_roe_q_differs_from_ttm(sample):
    """回归守卫：单季 ROE 与 TTM ROE 不能写成同一个公式。"""
    a = sample["factors"]["ROE_G_q"].to_numpy()
    b = sample["factors"]["ROE_G_ttm"].to_numpy()
    m = ~np.isnan(a) & ~np.isnan(b)
    assert m.sum() > 0
    assert np.mean(np.abs(a[m] - b[m]) > 1e-9) > 0.5


def test_no_zero_fill_artifacts(sample):
    """回归守卫：平台用 0 填充缺失财务值时，因子不应出现 -100% 的假值。"""
    bad = 0
    total = 0
    for f in sample["factors_raw"].values():
        a = f.to_numpy()
        m = ~np.isnan(a)
        total += int(m.sum())
        bad += int(np.isclose(a[m], -1.0).sum())
    assert total > 0
    assert bad / total < 1e-3, f"疑似 0 填充导致的假因子值: {bad}/{total}"
