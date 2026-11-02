"""截面预处理：去极值、标准化、行业中性化。"""

from __future__ import annotations

import numpy as np
import pandas as pd


def mad_winsorize(df: pd.DataFrame, k: float = 5.0) -> pd.DataFrame:
    """按截面（每一行=一个日期）做中位数 ±k×MAD 去极值。

    MAD = median(|x - median(x)|)
    """
    med = df.median(axis=1)
    mad = df.sub(med, axis=0).abs().median(axis=1)
    lower = med - k * mad
    upper = med + k * mad
    return df.clip(lower=lower, upper=upper, axis=0)


def zscore(df: pd.DataFrame) -> pd.DataFrame:
    """按截面做标准化。"""
    mean = df.mean(axis=1)
    std = df.std(axis=1).replace(0, np.nan)
    return df.sub(mean, axis=0).div(std, axis=0)


def industry_demean(df: pd.DataFrame, industry: pd.DataFrame) -> pd.DataFrame:
    """行业内去均值（行业中性化）。

    Parameters
    ----------
    df : 因子宽表（date × instrument）
    industry : 行业宽表（date × instrument），与 df 同形状
    """
    # 长表化：只保留两者都非空的样本
    f = df.stack().rename("factor")
    ind = industry.stack().rename("industry")
    m = pd.concat([f, ind], axis=1).dropna()
    if m.empty:
        return df.copy()

    date_level = m.index.get_level_values(0)
    m["factor"] = m["factor"] - m.groupby([date_level, "industry"])["factor"].transform("mean")

    out = m["factor"].unstack()
    return out.reindex(index=df.index, columns=df.columns)


def process(df: pd.DataFrame, industry: pd.DataFrame | None = None,
            k: float = 5.0, neutralize: bool = True) -> pd.DataFrame:
    """标准处理链：去极值 → 行业中性（可选）→ 标准化。"""
    out = mad_winsorize(df, k=k)
    if neutralize and industry is not None:
        out = industry_demean(out, industry)
    out = zscore(out)
    return out.replace([np.inf, -np.inf], np.nan)
