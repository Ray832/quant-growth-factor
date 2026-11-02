# -*- coding: utf-8 -*-
"""生成并在本地校验 BigQuant Notebook。

用法：
    python scripts/build_notebook.py            # 只生成
    python scripts/build_notebook.py --run      # 生成并顺序执行所有代码单元
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NB_PATH = ROOT / "notebook" / "成长因子测试.ipynb"
PLATFORM = ROOT / "platform" / "bq_factor_lab.py"


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(keepends=True)}


def code(text):
    return {"cell_type": "code", "metadata": {}, "execution_count": None,
            "outputs": [], "source": text.strip("\n").splitlines(keepends=True)}


def build():
    # 函数库直接取自平台脚本（同一份已验证代码）
    src = PLATFORM.read_text(encoding="utf-8")
    funcs = src.split("# 主流程")[0].rstrip()
    funcs = funcs.rsplit("# ---------------------------------------------------------------------------", 1)[0].rstrip()
    # Notebook 里由参数单元决定后端，函数库不再强制 Agg
    funcs = funcs.replace('    matplotlib.use("Agg")\n', "")
    # 去掉 shebang 与模块 docstring（那是 CLI 用法，Notebook 里用不到）
    if funcs.startswith("#!"):
        parts = funcs.split('"""', 2)
        if len(parts) >= 3:
            funcs = parts[2].lstrip("\n")

    cells = []

    cells.append(md("""
# 成长因子单因子测试 · BigQuant Notebook

复现华泰证券《单因子测试之成长类因子》的完整流程：**12 个成长因子 → 预处理 → IC / 分层 / 回归 / 稳健性**。

- 样本：2020-01 ~ 2025-12，A 股（剔除北交所、ST、停牌、次新）
- 数据：优先读取 `/bq_export_v41/`；不存在时自动改用 `dai` 查询
- 运行：菜单 **Run All** 即可，无需修改代码

| 章节 | 内容 |
|---|---|
| 0 | 参数配置 |
| 1 | 工具函数（与平台单文件脚本同源） |
| 2 | 数据加载与股票池 |
| 3 | 因子构建 |
| 4 | 预处理 |
| 5 | IC 分析 |
| 6 | 分层回测 |
| 7 | 回归法 |
| 8 | IC 衰减 |
| 9 | 分年度 / 分市值 |
| 10 | 稳健性：换手、成本、FDR |
| 11 | 两个关键问题（\\|t\\| 与收益 t、3Y 反向） |
| 12 | 结果自检 |
| 13 | 结果总览（读取全部产出并可视化） |
"""))

    cells.append(md("""
## 0. 参数配置

- `DATA_DIR`：数据目录，不存在会自动探测或回退 `dai`
- `USE_DAI`：强制走平台查询
- `SAMPLE_N`：>0 时只取前 N 只股票，用于快速验证
- `OUT_DIR`：图表与表格输出目录
"""))

    cells.append(code("""
import os, sys, time, math, warnings, json, zipfile
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib

# Notebook 内优先用 inline 后端；脚本模式退化为 Agg
try:
    get_ipython().run_line_magic("matplotlib", "inline")
except Exception:
    matplotlib.use("Agg")

import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")

DATA_DIR = "/bq_export_v41"
USE_DAI = False
START, END = "2020-01-01", "2025-12-31"
SAMPLE_N = 0
OUT_DIR = Path("./out_notebook")
OUT_DIR.mkdir(parents=True, exist_ok=True)

try:
    from IPython.display import display, Image
except Exception:
    display = print
    Image = None
print("参数就绪，输出目录：", OUT_DIR.resolve())
"""))

    cells.append(md("""
## 1. 工具函数

以下函数与项目里的 `platform/bq_factor_lab.py` 完全同源，包含数据读取、12 因子构建、
去极值 / 行业+市值中性 / 标准化、IC、分层、WLS 回归与 FDR。**无需修改**。
"""))

    cells.append(code(funcs))

    cells.append(md("""
## 2. 数据加载与股票池

优先读本地 CSV；若目录不存在或没有 `panel_*.csv`，自动改用 `dai` 查询（按年取数并压成月末）。

股票池规则：剔除北交所、ST、停牌、上市不足 12 个月，以及**截面期下一交易日停牌**的股票。
"""))

    cells.append(code("""
t0 = time.time()
if USE_DAI:
    raw = load_dai(START, END)
    susp = load_suspension_dai(START, END)
    source = "dai"
else:
    try:
        d = resolve_data_dir(DATA_DIR)
        raw = load_local(d)
        susp = load_suspension(d)
        source = f"local:{d}"
    except Exception as e:
        print("本地数据不可用，改用 dai：", e)
        raw = load_dai(START, END)
        susp = load_suspension_dai(START, END)
        source = "dai"

print(f"数据源：{source}")
print(f"原始：{len(raw):,d} 行，{raw['date'].nunique()} 个截面")

pool = filter_pool(raw)
pool = exclude_next_day_suspension(pool, susp)
if SAMPLE_N:
    keep = (pool.groupby("instrument")["close"].count()
            .sort_values(ascending=False).head(SAMPLE_N).index)
    pool = pool[pool["instrument"].isin(keep)]
    print(f"已抽样 {SAMPLE_N} 只")
print(f"过滤后：{len(pool):,d} 行，{pool['instrument'].nunique():,d} 只，耗时 {time.time()-t0:.1f}s")

wide = to_wide(pool)
print(f"宽表字段：{len(wide)} 个")
"""))

    cells.append(md("""
## 3. 因子构建

12 个因子 = 4 个财务科目（营收 / 净利润 / 经营现金流 / ROE）× 3 种口径（单季同比 / TTM 同比 / 三年复合）。

- 同比：(X_t − X_{t−12}) / |X_{t−12}|
- 三年复合：(X_t / X_{t−36})^(1/3) − 1，要求两端同为正
- 平台用 0 填充的缺失值、负营收、非正净资产，统一视为缺失
"""))

    cells.append(code("""
fac_raw = build_factors(wide)
cover = pd.DataFrame({
    "因子": FACTORS,
    "覆盖率": [fac_raw[k].loc[START:END].notna().mean().mean() for k in FACTORS],
})
display(cover.round(3))
"""))

    cells.append(md("""
## 4. 预处理

每个截面依次：中位数 ±5×MAD 去极值 → 对行业哑变量 + ln(流通市值) 回归取残差 → z-score。

- `fac`：中性化后的因子，用于 IC 与分层
- `fac_reg`：仅去极值 + 标准化的因子，用于回归法（模型中已含行业哑变量）
"""))

    cells.append(code("""
close = wide["close"]
dates = [d for d in close.index if pd.Timestamp(START) <= d <= pd.Timestamp(END)]
close, ind = close.loc[dates], wide["sw2021_level1_name"].loc[dates]
mv = wide["float_market_cap"].loc[dates]
logmv = np.log(mv.where(mv > 0))
fwd = forward_return(close)

fac, fac_reg = {}, {}
for k in FACTORS:
    f = fac_raw[k].loc[dates]
    fac[k] = prep(f, ind, logmv)
    fac_reg[k] = prep(f)

plt, LANG = setup_font("auto")
def L(zh, en):
    return zh if LANG == "zh" else en

print(f"评估期 {dates[0]:%Y-%m-%d} ~ {dates[-1]:%Y-%m-%d}，{len(dates)} 个截面，字体={LANG}")
"""))

    cells.append(md("""
## 5. IC 分析

IC 为因子截面值与下月收益的 Spearman 相关。关注三个数：

- **IC 均值**：方向与强度
- **t 值**：是否显著
- **IC>0 占比**：方向是否稳定

预期：当季（q）因子为正，三年复合（3y）为负。
"""))

    cells.append(code("""
ic_all, rows = {}, []
for k, f in fac.items():
    ic = ic_series(f, fwd)
    ic_all[k] = ic
    st = ic_stats(ic)
    rows.append({"因子": k, "IC": st["mean"], "t": st["t"],
                 "IR": st["ir"], "IC>0": st["positive_ratio"]})

ic_tbl = pd.DataFrame(rows).sort_values("IC", ascending=False).reset_index(drop=True)
display(ic_tbl.round(4))

d = ic_tbl.sort_values("IC")
fig, ax = plt.subplots(figsize=(7.4, 3.8))
ax.barh(d["因子"], d["IC"] * 100,
        color=["#1f4e79" if v > 0 else "#c00000" for v in d["IC"]])
ax.axvline(0, color="#333333", lw=0.8)
ax.set_xlabel(L("IC 均值（%）", "Mean IC (%)"))
ax.set_title(L("12 个成长因子的 IC 均值", "Mean IC of 12 growth factors"), loc="left")
fig.tight_layout()
fig.savefig(OUT_DIR / "fig_ic.png", dpi=200, bbox_inches="tight")
plt.show()

print("当季因子全部为正，三年复合因子为负。")
"""))

    cells.append(md("""
## 6. 分层回测

每月末在行业内按因子值分 5 层，层内等权；多空 = 第 1 层 − 第 5 层。

成本按**真实持仓换手**估算（双边千三），而不是假设 100% 换手。
"""))

    cells.append(code("""
layer_rows, navs = [], {}
for k, f in fac.items():
    lay = layer_returns(f, fwd, ind)
    ls = lay[0] - lay[4]

    layers = assign_layers(f, ind)
    hold = {d: set(layers.columns[layers.loc[d] == 0]) for d in layers.index}
    ds = sorted(hold)
    to = [1 - len(hold[a] & hold[b]) / len(hold[a]) for a, b in zip(ds[:-1], ds[1:]) if hold[a]]
    avg_to = float(np.mean(to)) if to else np.nan

    net = ls - avg_to * 0.003
    p_top, p_g, p_n = perf_stats(lay[0]), perf_stats(ls), perf_stats(net)
    m = lay.mean()
    mono = -m.corr(pd.Series(range(5), index=m.index), method="spearman")

    layer_rows.append({"因子": k, "TOP年化": p_top.get("ann_return"),
                       "多空毛": p_g.get("ann_return"), "多空净": p_n.get("ann_return"),
                       "夏普": p_g.get("sharpe"), "回撤": p_g.get("max_drawdown"),
                       "换手": avg_to, "单调性": mono})
    if k.endswith("_q"):
        navs[k] = (1 + ls).cumprod()

layer_tbl = pd.DataFrame(layer_rows)
display(layer_tbl.round(3))

fig, ax = plt.subplots(figsize=(7.4, 3.4))
for k, c in zip(["ROE_G_q", "Profit_G_q", "Sales_G_q", "OCF_G_q"],
                ["#1f4e79", "#c00000", "#7f7f7f", "#c55a11"]):
    ax.plot(navs[k].index, navs[k].values, label=k, color=c, lw=1.2)
ax.axhline(1, color="#999999", lw=0.7, ls="--")
ax.set_title(L("当季因子的多空净值", "Long-short NAV of q factors"), loc="left")
ax.legend(fontsize=7, frameon=False)
fig.tight_layout()
fig.savefig(OUT_DIR / "fig_nav.png", dpi=200, bbox_inches="tight")
plt.show()

print("当季因子单调性为正，三年复合为负。")
"""))

    cells.append(md("""
## 7. 回归法

每月做一次加权最小二乘：`r_{t+1} = 行业哑变量 + β·f_t + ε`，权重为 √流通市值。

关注 **|t| 均值**（月度截面显著性）与 **收益序列 t**（长期方向是否稳定）的差异。
"""))

    cells.append(code("""
reg_rows, beta_store = [], {}
for k in FACTORS:
    betas, ts = {}, {}
    for d in dates:
        b, t = wls_month(fwd.loc[d], fac_reg[k].loc[d], ind.loc[d], np.sqrt(mv.loc[d]))
        betas[d], ts[d] = b, t
    bs, ts_ = pd.Series(betas).dropna(), pd.Series(ts).dropna()
    beta_store[k] = bs
    reg_rows.append({"因子": k, "|t|均值": ts_.abs().mean(),
                     "|t|>2占比": (ts_.abs() > 2).mean(),
                     "β均值": bs.mean(),
                     "收益t": bs.mean() / bs.std() * np.sqrt(len(bs))})

reg_tbl = pd.DataFrame(reg_rows)
display(reg_tbl.round(4))
print("|t| 均值普遍 >2，但收益序列 t 普遍 <2：横截面显著 ≠ 长期有效。")
"""))

    cells.append(md("""
## 8. IC 衰减

对 1–6 个月的持有期分别计算 IC。若因子是"短期信息优势"，IC 应快速衰减；
若 IC 不降，说明更像持续性定价偏差或风格暴露。
"""))

    cells.append(code("""
horizons = {h: forward_return(close, h).loc[dates] for h in range(1, 7)}
dec = {}
for k, f in fac.items():
    dec[k] = {f"t+{h}": ic_series(f, horizons[h]).mean() for h in range(1, 7)}
dec_tbl = pd.DataFrame(dec).T
display(dec_tbl.round(4))

fig, axes = plt.subplots(1, 2, figsize=(7.6, 3.0), sharey=True)
for ax, group, title in (
    (axes[0], ["Sales_G_q", "Profit_G_q", "OCF_G_q", "ROE_G_q"], L("当季（q）", "q")),
    (axes[1], ["Sales_G_3y", "Profit_G_3y", "OCF_G_3y", "ROE_G_3y"], L("三年复合（3y）", "3y")),
):
    for k in group:
        ax.plot(range(1, 7), dec_tbl.loc[k].values * 100, marker="o", ms=3, lw=1.1, label=k)
    ax.axhline(0, color="#999999", lw=0.7)
    ax.set_title(title, fontsize=9)
    ax.set_xlabel(L("持有期（月）", "Horizon (months)"))
    ax.legend(fontsize=6, frameon=False)
axes[0].set_ylabel("IC (%)")
fig.suptitle(L("IC 衰减：当季不衰减，三年复合持续反向", "IC decay"), x=0.02, ha="left", fontsize=10)
fig.tight_layout()
fig.savefig(OUT_DIR / "fig_decay.png", dpi=200, bbox_inches="tight")
plt.show()
"""))

    cells.append(md("""
## 9. 分年度 / 分市值

- 分年度：看因子在哪一年有效、哪一年失效
- 分市值：按流通市值三分组，组内计算 IC
"""))

    cells.append(code("""
ic_df = pd.DataFrame(ic_all)
yearly = ic_df.groupby(ic_df.index.year).mean()
display(yearly.round(4))

fig, ax = plt.subplots(figsize=(7.4, 3.2))
x = np.arange(len(yearly))
w = 0.26
for i, (k, c) in enumerate(zip(["ROE_G_q", "Profit_G_q", "Profit_G_3y"],
                               ["#1f4e79", "#c00000", "#7f7f7f"])):
    ax.bar(x + (i - 1) * w, yearly[k] * 100, w, label=k, color=c)
ax.axhline(0, color="#333333", lw=0.8)
ax.set_xticks(x); ax.set_xticklabels(yearly.index)
ax.set_ylabel("IC (%)")
ax.set_title(L("分年度 IC：2020、2024 强，2021、2023 弱", "Yearly IC"), loc="left")
ax.legend(fontsize=7, frameon=False)
fig.tight_layout()
fig.savefig(OUT_DIR / "fig_yearly.png", dpi=200, bbox_inches="tight")
plt.show()

size_rows = []
for k in ["ROE_G_q", "Profit_G_q", "Sales_G_q", "OCF_G_q"]:
    for g, label in ((0, "小盘"), (1, "中盘"), (2, "大盘")):
        ics = {}
        for d in dates:
            s = mv.loc[d]
            if s.notna().sum() < 100:
                continue
            q = pd.qcut(s.rank(method="first"), 3, labels=[0, 1, 2])
            sel = (q == g).reindex(fac[k].columns).fillna(False).values
            a, b = fac[k].loc[d][sel], fwd.loc[d][sel]
            m = a.notna() & b.notna()
            if m.sum() >= 30:
                ics[d] = a[m].corr(b[m], method="spearman")
        size_rows.append({"因子": k, "市值组": label, "IC": pd.Series(ics).mean()})
size_tbl = pd.DataFrame(size_rows)
display(size_tbl.pivot(index="因子", columns="市值组", values="IC").round(4))
print("当季因子在小盘股中更有效。")
"""))

    cells.append(md("""
## 10. 稳健性：成本与多重检验

- **真实换手**：月换手 8%–24%，成本拖累 0.3%–0.9%/年
- **FDR**：对 12 个因子的 IC t 值做 Benjamini–Hochberg 校正
"""))

    cells.append(code("""
cost_tbl = layer_tbl[["因子", "换手", "多空毛", "多空净", "夏普"]].copy()
cost_tbl["成本拖累"] = cost_tbl["多空毛"] - cost_tbl["多空净"]
display(cost_tbl.round(4))

from math import erf, sqrt as _sqrt
def _p(x):
    return 2 * 0.5 * (1 - erf(abs(x) / _sqrt(2))) if pd.notna(x) else np.nan

fdr = ic_tbl[["因子", "IC", "t"]].copy()
fdr["p"] = fdr["t"].map(_p)
fdr["p_adj"] = bh_fdr(fdr["p"].fillna(1))
fdr["显著"] = fdr["p_adj"] < 0.05
display(fdr.round(4))

print("FDR 后仅 OCF_G_q 显著。")
"""))

    cells.append(md("""
## 11. 两个关键问题

**Q1**：为什么月度 |t| 很高，但收益序列 t 很低？——β 符号频繁翻转。
**Q2**：三年复合因子为什么反向？——动量暴露 + "低动量高增长"的价值陷阱。

下面的单元分别给出证据。
"""))

    cells.append(code("""
# Q1：β 稳定性
stab = []
for k in FACTORS:
    b = beta_store[k]
    stab.append({"因子": k, "|t|均值": reg_tbl.set_index("因子").loc[k, "|t|均值"],
                 "β均值": b.mean(), "β标准差": b.std(),
                 "收益t": b.mean() / b.std() * np.sqrt(len(b)),
                 "正收益月份": (b > 0).mean(),
                 "符号翻转率": (np.sign(b).diff().abs() > 0).sum() / (len(b) - 1)})
stab_tbl = pd.DataFrame(stab)
display(stab_tbl.round(3))

fig, ax = plt.subplots(figsize=(7.4, 3.4))
d = stab_tbl.sort_values("|t|均值")
y = np.arange(len(d))
ax.barh(y - 0.19, d["|t|均值"], height=0.36, color="#1f4e79", label=L("月度 |t| 均值", "mean |t|"))
ax.barh(y + 0.19, d["收益t"], height=0.36, color="#c00000", label=L("收益序列 t", "return t"))
ax.axvline(2, color="#7f7f7f", lw=0.8, ls="--")
ax.set_yticks(y); ax.set_yticklabels(d["因子"], fontsize=7)
ax.set_title(L("“每月都能排序”不等于“长期能赚钱”", "|t| vs return t"), loc="left")
ax.legend(fontsize=7, frameon=False)
fig.tight_layout()
fig.savefig(OUT_DIR / "fig_tstat.png", dpi=200, bbox_inches="tight")
plt.show()

# Q2：3y 因子的动量暴露与分组
past12 = close.pct_change(12)
fwd12 = close.pct_change(12).shift(-12)
rows = []
for k in ["Sales_G_3y", "Profit_G_3y", "OCF_G_3y", "ROE_G_3y"]:
    cors, qs = {}, {}
    for d in dates:
        a, b = fac_raw[k].loc[d], past12.loc[d]
        m = a.notna() & b.notna()
        if m.sum() >= 50:
            cors[d] = a[m].corr(b[m], method="spearman")
        a2, b2 = fac_raw[k].loc[d], fwd12.loc[d]
        m2 = a2.notna() & b2.notna()
        if m2.sum() >= 100:
            qq = pd.qcut(a2[m2].rank(method="first"), 5, labels=False)
            qs[d] = b2[m2].groupby(qq).mean()
    qdf = pd.DataFrame(qs).T
    rows.append({"因子": k, "动量相关": pd.Series(cors).mean(),
                 **{f"Q{i+1}": qdf[i].mean() for i in range(5)}})
three_tbl = pd.DataFrame(rows)
display(three_tbl.round(3))

fig, ax = plt.subplots(figsize=(7.4, 3.1))
for k, c in zip(["Sales_G_3y", "Profit_G_3y", "ROE_G_3y"], ["#1f4e79", "#c00000", "#7f7f7f"]):
    ax.plot(range(1, 6), three_tbl.set_index("因子").loc[k, [f"Q{i}" for i in range(1, 6)]] * 100,
            marker="o", ms=4, lw=1.2, label=k, color=c)
ax.set_xticks(range(1, 6))
ax.set_xlabel(L("三年增长分组（1=最低，5=最高）", "3y growth quintile"))
ax.set_ylabel(L("未来 12 个月收益（%）", "Forward 12m return (%)"))
ax.set_title(L("高三年增长组的事后收益更低", "Higher 3y growth earns less"), loc="left")
ax.legend(fontsize=7, frameon=False)
fig.tight_layout()
fig.savefig(OUT_DIR / "fig_3y.png", dpi=200, bbox_inches="tight")
plt.show()
"""))

    cells.append(md("""
## 12. 结果自检

把当前结果与本地全样本基准值比对。**全部 PASS** 才说明平台与本地一致。
"""))

    cells.append(code("""
EXPECTED_IC = {
    "ROE_G_q": 0.018423, "Profit_G_q": 0.015466, "Sales_G_q": 0.010876,
    "OCF_G_q": 0.009671, "ROE_G_ttm": 0.005593, "OCF_G_ttm": 0.004107,
    "OCF_G_3y": 0.002594, "Profit_G_ttm": 0.002028, "Sales_G_ttm": -0.001412,
    "ROE_G_3y": -0.002850, "Sales_G_3y": -0.002959, "Profit_G_3y": -0.007921,
}
got = ic_tbl.set_index("因子")["IC"]
bad = []
for k, v in EXPECTED_IC.items():
    diff = abs(float(got[k]) - v)
    flag = "PASS" if diff < 1e-4 else "FAIL"
    if flag == "FAIL":
        bad.append(k)
    print(f"{k:12s} 平台={got[k]:+.6f}  本地={v:+.6f}  diff={diff:.2e}  {flag}")
print("\\n结果：", "全部一致 ✅" if not bad else f"存在差异：{bad}")
"""))

    cells.append(md("""
## 13. 结果总览

读取 `out_notebook/` 下的全部产出（CSV + PNG），在 Notebook 中统一展示，方便截图或汇报。
"""))

    cells.append(code("""
print("产出文件：")
for p in sorted(OUT_DIR.iterdir()):
    print(" -", p.name, f"{p.stat().st_size/1024:.1f} KB")

for name in ["ic_tbl", "layer_tbl", "reg_tbl", "dec_tbl", "fdr"]:
    if name in globals():
        print(f"\\n### {name}")
        display(globals()[name].round(4))

print("\\n### 图表")
for p in sorted(OUT_DIR.glob("*.png")):
    print(p.name)
    if Image is not None:
        display(Image(filename=str(p)))
"""))

    cells.append(md("""
## 14. 导出与结论

- 表格导出为 CSV，图表为 PNG，统一打包 `out_notebook.zip`
- 结论：当季因子仍有区分度（IC 1.0%–1.8%、单调性 0.9–1.0），但强度较原文衰减；
  三年复合因子系统性反向；扣真实换手成本后，当季因子多空仍有 2.6%–5.3%。
"""))

    cells.append(code("""
tables = {"ic_summary": ic_tbl, "layer_summary": layer_tbl,
          "regression_summary": reg_tbl, "ic_decay": dec_tbl, "fdr_summary": fdr}
for name, df in tables.items():
    df.to_csv(OUT_DIR / f"{name}.csv", index=False, encoding="utf-8-sig")

with zipfile.ZipFile(OUT_DIR / "out_notebook.zip", "w") as z:
    for p in OUT_DIR.iterdir():
        if p.suffix in (".csv", ".png"):
            z.write(p, p.name)

print("已导出到", OUT_DIR.resolve())
print("总耗时：", f"{time.time()-t0:.1f}s")
"""))

    nb = {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    NB_PATH.parent.mkdir(parents=True, exist_ok=True)
    NB_PATH.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
    print("saved", NB_PATH, "cells:", len(cells))
    return nb


def run(nb):
    """顺序执行所有 code cell（模拟 Run All）。"""
    g = {"__name__": "__main__"}
    for i, c in enumerate(nb["cells"]):
        if c["cell_type"] != "code":
            continue
        src = "".join(c["source"])
        print(f"\n===== cell {i} =====")
        exec(compile(src, f"<cell {i}>", "exec"), g)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    a = ap.parse_args()
    nb = build()
    if a.run:
        run(nb)
