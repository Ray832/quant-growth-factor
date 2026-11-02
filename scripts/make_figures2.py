# -*- coding: utf-8 -*-
"""补充图：因子相关性热力图、行业成长分布。"""

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

FIG = ROOT / "report" / "figures"
T = ROOT / "output" / "tables"

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 150


def note(fig):
    fig.text(0.01, 0.01, "资料来源：BigQuant，项目复现计算", fontsize=7, color="#7f7f7f")


def main():
    corr = pd.read_csv(T / "factor_corr.csv", index_col=0)
    fig, ax = plt.subplots(figsize=(7.4, 6.0))
    im = ax.imshow(corr.values, cmap="RdBu_r", vmin=-0.4, vmax=0.4)
    ax.set_xticks(range(len(corr)))
    ax.set_yticks(range(len(corr)))
    ax.set_xticklabels(corr.columns, rotation=90, fontsize=7)
    ax.set_yticklabels(corr.index, fontsize=7)
    for i in range(len(corr)):
        for j in range(len(corr)):
            v = corr.values[i, j]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=5.2,
                    color="white" if abs(v) > 0.25 else "#333333")
    fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
    ax.set_title("12 个成长因子的截面相关性（月度均值）", fontsize=10, loc="left")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    note(fig)
    fig.savefig(FIG / "fig9_corr.png", dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    ind = pd.read_csv(T / "industry_growth.csv", index_col=0).sort_values("Sales_G_ttm")
    fig, ax = plt.subplots(figsize=(7.2, 6.4))
    y = np.arange(len(ind))
    ax.barh(y, ind["Sales_G_ttm"] * 100, color="#1f4e79", height=0.65)
    ax.set_yticks(y)
    ax.set_yticklabels(ind.index, fontsize=7)
    ax.axvline(0, color="#333333", lw=0.8)
    ax.set_xlabel("营业收入 TTM 同比中位数（%）")
    ax.set_title("行业成长差异显著（2025-12 截面）", fontsize=10, loc="left")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    note(fig)
    fig.savefig(FIG / "fig10_industry.png", dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("saved fig9, fig10")


if __name__ == "__main__":
    main()
