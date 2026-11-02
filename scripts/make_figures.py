# -*- coding: utf-8 -*-
"""生成研报图表（券商风格，300 dpi）。"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import config, data, evaluate, factors, preprocess  # noqa: E402

FIG = ROOT / "report" / "figures"
FIG.mkdir(parents=True, exist_ok=True)

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["axes.edgecolor"] = "#888888"
plt.rcParams["axes.linewidth"] = 0.8
plt.rcParams["figure.dpi"] = 150

BLUE, RED, GRAY, ORANGE = "#1f4e79", "#c00000", "#7f7f7f", "#c55a11"


def note(fig):
    fig.text(0.01, 0.01, "资料来源：BigQuant，项目复现计算", fontsize=7, color=GRAY)


def save(fig, name):
    note(fig)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(FIG / name, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("saved", name)


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
    close = close.loc[dates]
    ind = wide["sw2021_level1_name"].loc[dates]
    mv = wide["float_market_cap"].loc[dates]
    logmv = np.log(mv.where(mv > 0))
    fwd = evaluate.forward_return(close)

    fac_raw = {k: v.loc[dates] for k, v in factors.build_factors(wide).items()}
    fac = {}
    for k, f in fac_raw.items():
        x = preprocess.zscore(preprocess.mad_winsorize(f, k=config.MAD_K))
        fac[k] = residualize(x, ind, logmv)

    # 中性 IC 序列（供报告与图表复用）
    ic_all = {k: evaluate.ic_series(v, fwd) for k, v in fac.items()}
    pd.DataFrame(ic_all).to_csv(config.OUT_DIR / "tables" / "ic_series_neutral.csv",
                                encoding="utf-8-sig", index_label="date")

    # --- 图1：IC 柱状 ---
    ic_mean = pd.Series({k: v.mean() for k, v in ic_all.items()}).sort_values()
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    colors = [BLUE if v > 0 else RED for v in ic_mean.values]
    ax.barh(ic_mean.index, ic_mean.values * 100, color=colors, height=0.62)
    ax.axvline(0, color="#333333", lw=0.8)
    ax.set_xlabel("IC 均值（%）")
    ax.set_title("12 个成长因子的 IC 均值（2020–2025）", fontsize=10, loc="left")
    for i, v in enumerate(ic_mean.values * 100):
        ax.text(v + (0.02 if v >= 0 else -0.02), i, f"{v:+.2f}",
                va="center", ha="left" if v >= 0 else "right", fontsize=7)
    ax.set_xlim(min(ic_mean.values * 100) - 0.5, max(ic_mean.values * 100) + 0.5)
    save(fig, "fig1_ic_bar.png")

    # --- 图2：多空净值 ---
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    for k, c in (("ROE_G_q", BLUE), ("Profit_G_q", RED), ("Sales_G_q", GRAY), ("OCF_G_q", ORANGE)):
        lay = evaluate.layer_returns(fac[k], fwd, ind, n=5)
        ls = (lay[0] - lay[4]).fillna(0)
        nav = (1 + ls).cumprod()
        ax.plot(nav.index, nav.values, label=k, color=c, lw=1.3)
    ax.axhline(1, color="#999999", lw=0.7, ls="--")
    ax.set_title("当季因子的多空组合净值（5 层，行业中性）", fontsize=10, loc="left")
    ax.legend(fontsize=7, frameon=False)
    save(fig, "fig2_nav.png")

    # --- 图3：IC 衰减 ---
    dec = pd.read_csv(config.OUT_DIR / "tables" / "ic_decay.csv").set_index("factor")
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 2.9), sharey=True)
    for ax, group, title in ((axes[0], ["Sales_G_q", "Profit_G_q", "OCF_G_q", "ROE_G_q"], "当季（q）"),
                             (axes[1], ["Sales_G_3y", "Profit_G_3y", "OCF_G_3y", "ROE_G_3y"], "三年复合（3y）")):
        for k in group:
            ax.plot(range(1, 7), dec.loc[k, [f"IC_t{i}" for i in range(1, 7)]] * 100,
                    marker="o", ms=3, lw=1.2, label=k)
        ax.axhline(0, color="#999999", lw=0.7)
        ax.set_title(title, fontsize=9)
        ax.set_xlabel("持有期（月）")
        ax.legend(fontsize=6, frameon=False)
    axes[0].set_ylabel("IC（%）")
    fig.suptitle("IC 衰减：当季不衰减，三年复合持续反向", fontsize=10, x=0.02, ha="left")
    save(fig, "fig3_decay.png")

    # --- 图4：分年度 IC ---
    icdf = pd.DataFrame(ic_all)
    yearly = icdf.groupby(icdf.index.year).mean()
    sel = ["ROE_G_q", "Profit_G_q", "Profit_G_3y"]
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    x = np.arange(len(yearly.index))
    w = 0.26
    for i, (k, c) in enumerate(zip(sel, (BLUE, RED, GRAY))):
        ax.bar(x + (i - 1) * w, yearly[k] * 100, w, label=k, color=c)
    ax.axhline(0, color="#333333", lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(yearly.index, fontsize=8)
    ax.set_ylabel("IC 均值（%）")
    ax.set_title("分年度 IC：2020、2024 强，2021、2023 弱", fontsize=10, loc="left")
    ax.legend(fontsize=7, frameon=False)
    save(fig, "fig4_yearly.png")

    # --- 图5：|t| 与 beta t ---
    dd = pd.read_csv(config.OUT_DIR / "tables" / "deepdive_beta.csv").set_index("factor")
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    order = dd["abs_t_mean"].sort_values().index
    y = np.arange(len(order))
    ax.barh(y - 0.19, dd.loc[order, "abs_t_mean"], height=0.36, color=BLUE, label="月度 |t| 均值")
    ax.barh(y + 0.19, dd.loc[order, "beta_t"], height=0.36, color=RED, label="因子收益序列 t 值")
    ax.axvline(2, color=GRAY, lw=0.8, ls="--")
    ax.axvline(0, color="#333333", lw=0.8)
    ax.set_yticks(y)
    ax.set_yticklabels(order, fontsize=7)
    ax.set_title("“每月都能排序”不等于“长期能赚钱”", fontsize=10, loc="left")
    ax.legend(fontsize=7, frameon=False, loc="lower right")
    save(fig, "fig5_tstat.png")

    # --- 图6：3y 五分组事后收益 ---
    q = pd.read_csv(config.OUT_DIR / "tables" / "deepdive_3y_quintile.csv").set_index("factor")
    fig, ax = plt.subplots(figsize=(7.2, 3.1))
    x = np.arange(5)
    for k, c in zip(["Sales_G_3y", "Profit_G_3y", "ROE_G_3y"], (BLUE, RED, GRAY)):
        ax.plot(x + 1, q.loc[k, [f"Q{i}" for i in range(1, 6)]] * 100, marker="o", ms=4, lw=1.2,
                label=k, color=c)
    ax.set_xticks(range(1, 6))
    ax.set_xlabel("三年复合增长率分组（1=最低，5=最高）")
    ax.set_ylabel("未来 12 个月平均收益（%）")
    ax.set_title("高三年增长组的事后收益更低", fontsize=10, loc="left")
    ax.legend(fontsize=7, frameon=False)
    save(fig, "fig6_3y_quintile.png")

    # --- 图7：3y 按动量分组 IC ---
    mg = pd.read_csv(config.OUT_DIR / "tables" / "deepdive_3y_momentum.csv")
    piv = mg.pivot(index="factor", columns="momentum_group", values="ic_mean")[["low", "mid", "high"]]
    fig, ax = plt.subplots(figsize=(7.2, 3.1))
    x = np.arange(len(piv.index))
    w = 0.26
    for i, (g, c, label) in enumerate((("low", RED, "低动量组"), ("mid", GRAY, "中动量组"), ("high", BLUE, "高动量组"))):
        ax.bar(x + (i - 1) * w, piv[g] * 100, w, color=c, label=label)
    ax.axhline(0, color="#333333", lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(piv.index, fontsize=8)
    ax.set_ylabel("3y 因子 IC（%）")
    ax.set_title("3y 因子的反向集中在“低动量 + 高增长”组", fontsize=10, loc="left")
    ax.legend(fontsize=7, frameon=False)
    save(fig, "fig7_3y_momentum.png")

    # --- 图8：分市值 IC ---
    sz = pd.read_csv(config.OUT_DIR / "tables" / "size_ic_summary.csv")
    piv = sz.pivot(index="factor", columns="size", values="ic_mean")[["small", "mid", "large"]]
    sel = ["ROE_G_q", "Profit_G_q", "Sales_G_q", "OCF_G_q"]
    piv = piv.loc[sel]
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    x = np.arange(len(piv.index))
    for i, (g, c, label) in enumerate((("small", BLUE, "小盘"), ("mid", GRAY, "中盘"), ("large", RED, "大盘"))):
        ax.bar(x + (i - 1) * w, piv[g] * 100, w, color=c, label=label)
    ax.axhline(0, color="#333333", lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(piv.index, fontsize=8)
    ax.set_ylabel("IC（%）")
    ax.set_title("当季因子在小盘股中更有效", fontsize=10, loc="left")
    ax.legend(fontsize=7, frameon=False)
    save(fig, "fig8_size_ic.png")


if __name__ == "__main__":
    main()
