# -*- coding: utf-8 -*-
"""补充图：24 个月滚动 IC。"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
T = ROOT / "output" / "tables"
FIG = ROOT / "report" / "figures"

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 150

ic = pd.read_csv(T / "ic_series_neutral.csv", index_col=0, parse_dates=True)
roll = ic.rolling(24).mean()

fig, ax = plt.subplots(figsize=(7.4, 3.3))
for k, c in (("ROE_G_q", "#1f4e79"), ("Profit_G_q", "#c00000"),
             ("Sales_G_q", "#7f7f7f"), ("Profit_G_3y", "#c55a11")):
    ax.plot(roll.index, roll[k] * 100, lw=1.2, color=c, label=k)
ax.axhline(0, color="#333333", lw=0.8)
ax.set_ylabel("24 个月滚动 IC（%）")
ax.set_title("滚动 IC：2022 年后当季因子走弱、三年复合持续为负", fontsize=10, loc="left")
ax.legend(fontsize=7, frameon=False, ncol=2)
fig.text(0.01, 0.01, "资料来源：BigQuant，项目复现计算", fontsize=7, color="#7f7f7f")
fig.tight_layout(rect=(0, 0.03, 1, 1))
fig.savefig(FIG / "fig11_rolling.png", dpi=300, bbox_inches="tight", facecolor="white")
print("saved fig11")
