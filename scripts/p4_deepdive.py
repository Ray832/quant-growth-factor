# -*- coding: utf-8 -*-
"""P4 前置：两个关键问题的深挖分析。

Q1：为什么回归的 |t| 均值很高，但因子收益率序列的 t 值很低？
Q2：为什么三年复合增长率因子（3y）系统性反向？

输出：
    output/tables/deepdive_beta.csv        各因子 beta 的稳定性指标
    output/tables/deepdive_beta_corr.csv   |t| 与 beta t 的横向关系
    output/tables/deepdive_3y.csv          3y 因子的动量暴露与持续性
    output/tables/deepdive_3y_momentum.csv 按过去 12 月收益分组的 3y IC
    output/tables/deepdive_3y_quintile.csv 3y 五分组的事后收益
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import config, data, evaluate, factors, preprocess  # noqa: E402


def main():
    raw = data.load_panel()
    pool = data.apply_next_day_suspension(data.filter_pool(raw))
    wide = data.to_wide(pool)
    close = wide["close"]

    start, end = pd.Timestamp(config.EVAL_START), pd.Timestamp(config.EVAL_END)
    dates = [d for d in close.index if start <= d <= end]
    close = close.loc[dates]
    ind = wide["sw2021_level1_name"].loc[dates]
    mv = wide["float_market_cap"].loc[dates]
    logmv = np.log(mv.where(mv > 0))
    fwd1 = evaluate.forward_return(close)

    fac = {k: v.loc[dates] for k, v in factors.build_factors(wide).items()}

    # ------------------------------------------------------------------
    # Q1：beta 稳定性
    # ------------------------------------------------------------------
    reg = pd.read_csv(config.OUT_DIR / "tables" / "regression_series.csv",
                      index_col=0, parse_dates=True)
    summ = pd.read_csv(config.OUT_DIR / "tables" / "regression_summary.csv").set_index("factor")

    rows = []
    for name in config.FACTORS:
        beta = reg[f"{name}_beta"].dropna()
        t = reg[f"{name}_t"].dropna()
        flip = int((np.sign(beta).diff().abs() > 0).sum())
        rows.append({
            "factor": name,
            "beta_mean": beta.mean(),
            "beta_std": beta.std(),
            "beta_t": beta.mean() / beta.std() * np.sqrt(len(beta)),
            "pos_months": (beta > 0).mean(),
            "sign_flips": flip,
            "flip_rate": flip / max(len(beta) - 1, 1),
            "beta_ac1": beta.autocorr(1),
            "abs_t_mean": summ.loc[name, "abs_t_mean"],
            "year2020": beta[beta.index.year == 2020].mean(),
            "year2021": beta[beta.index.year == 2021].mean(),
            "year2022": beta[beta.index.year == 2022].mean(),
            "year2023": beta[beta.index.year == 2023].mean(),
            "year2024": beta[beta.index.year == 2024].mean(),
            "year2025": beta[beta.index.year == 2025].mean(),
        })
    beta_tbl = pd.DataFrame(rows)
    beta_tbl.to_csv(config.OUT_DIR / "tables" / "deepdive_beta.csv",
                    index=False, encoding="utf-8-sig")

    corr_tbl = pd.DataFrame([{
        "corr_absT_betaT": beta_tbl["abs_t_mean"].corr(beta_tbl["beta_t"]),
        "corr_absT_pos": beta_tbl["abs_t_mean"].corr(beta_tbl["pos_months"]),
        "mean_absT": beta_tbl["abs_t_mean"].mean(),
        "mean_beta_t": beta_tbl["beta_t"].mean(),
        "mean_flip_rate": beta_tbl["flip_rate"].mean(),
    }])
    corr_tbl.to_csv(config.OUT_DIR / "tables" / "deepdive_beta_corr.csv",
                    index=False, encoding="utf-8-sig")

    print("Q1 beta 稳定性")
    print(beta_tbl[["factor", "abs_t_mean", "beta_t", "pos_months", "flip_rate",
                    "year2020", "year2023", "year2024"]].round(3).to_string(index=False))
    print(corr_tbl.round(3).to_string(index=False))

    # ------------------------------------------------------------------
    # Q2：3y 因子为什么反向
    # ------------------------------------------------------------------
    past12 = close.pct_change(12)          # 过去 12 个月收益（动量）
    fwd12 = close.pct_change(12).shift(-12)  # 未来 12 个月收益
    p3 = ["Sales_G_3y", "Profit_G_3y", "OCF_G_3y", "ROE_G_3y"]

    def neutralize(f):
        x = preprocess.zscore(preprocess.mad_winsorize(f, k=config.MAD_K))
        # 与 P2 一致的残差化：行业 + ln 市值
        out = {}
        for d in x.index:
            s, i, m = x.loc[d], ind.loc[d], logmv.loc[d]
            mask = s.notna() & i.notna() & m.notna()
            if mask.sum() < 50:
                continue
            X = pd.get_dummies(i[mask], drop_first=True).astype(float)
            X.insert(0, "const", 1.0)
            X["logmv"] = m[mask].values
            y = s[mask].to_numpy()
            b, *_ = np.linalg.lstsq(X.to_numpy(), y, rcond=None)
            out[d] = pd.Series(y - X.to_numpy() @ b, index=s[mask].index)
        return pd.DataFrame(out).T.reindex(index=x.index, columns=x.columns)

    rows_mom, rows_momgroup, rows_quin = [], [], []

    for name in p3:
        f = fac[name]
        fn = neutralize(f)

        # 与过去 12 月收益的截面相关（动量暴露）
        cors = {}
        for d in dates:
            a, b = f.loc[d], past12.loc[d]
            m = a.notna() & b.notna()
            if m.sum() >= 50:
                cors[d] = a[m].corr(b[m], method="spearman")
        mom = pd.Series(cors)

        # 增长持续性：3y 因子与一年后的 3y 因子的相关、与变化的相关
        f12 = f.shift(-12)
        pers = {}
        for d in dates:
            a, b = f.loc[d], f12.loc[d]
            m = a.notna() & b.notna()
            if m.sum() >= 50:
                pers[d] = a[m].corr(b[m], method="spearman")
        persistence = pd.Series(pers)

        # 按动量分组后的 3y IC
        for grp, label in ((0, "low"), (1, "mid"), (2, "high")):
            ics = {}
            for d in dates:
                pr = past12.loc[d]
                if pr.notna().sum() < 100:
                    continue
                q = pd.qcut(pr.rank(method="first"), 3, labels=[0, 1, 2])
                sel = (q == grp).reindex(fn.columns).fillna(False).values
                a, b = fn.loc[d][sel], fwd1.loc[d][sel]
                m = a.notna() & b.notna()
                if m.sum() >= 30:
                    ics[d] = a[m].corr(b[m], method="spearman")
            rows_momgroup.append({"factor": name, "momentum_group": label,
                                  "ic_mean": pd.Series(ics).mean()})

        # 3y 五分组的事后 12 月收益
        qrows = {}
        for d in dates:
            a, b = f.loc[d], fwd12.loc[d]
            m = a.notna() & b.notna()
            if m.sum() < 100:
                continue
            q = pd.qcut(a[m].rank(method="first"), 5, labels=False)
            r = b[m].groupby(q).mean()
            qrows[d] = r
        qdf = pd.DataFrame(qrows).T
        rows_quin.append({"factor": name,
                          **{f"Q{i+1}": qdf[i].mean() for i in range(5)}})

        rows_mom.append({
            "factor": name,
            "momentum_corr_mean": mom.mean(),
            "momentum_corr_pos": (mom > 0).mean(),
            "persistence": persistence.mean(),
        })

    mom_tbl = pd.DataFrame(rows_mom)
    mom_tbl.to_csv(config.OUT_DIR / "tables" / "deepdive_3y.csv",
                   index=False, encoding="utf-8-sig")
    pd.DataFrame(rows_momgroup).to_csv(config.OUT_DIR / "tables" / "deepdive_3y_momentum.csv",
                                       index=False, encoding="utf-8-sig")
    pd.DataFrame(rows_quin).to_csv(config.OUT_DIR / "tables" / "deepdive_3y_quintile.csv",
                                   index=False, encoding="utf-8-sig")

    print("\nQ2 3y 动量暴露与持续性")
    print(mom_tbl.round(4).to_string(index=False))
    print("\n按动量分组的 3y IC")
    print(pd.DataFrame(rows_momgroup).pivot(index="factor", columns="momentum_group",
                                            values="ic_mean").round(4).to_string())
    print("\n3y 五分组事后 12 月收益")
    print(pd.DataFrame(rows_quin).round(4).to_string(index=False))


if __name__ == "__main__":
    main()
