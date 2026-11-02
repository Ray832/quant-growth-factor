"""12 个成长因子的构建。

口径（与研报对齐，2020–2025 评估期）：
    *_G_q    单季值同比     f(t) / f(t-12m) - 1
    *_G_ttm  TTM 同比       f(t) / f(t-12m) - 1
    *_G_3y   TTM 三年复合   (f(t) / f(t-36m))^(1/3) - 1
    ROE      net_profit_ttm / 归母净资产（研报口径的 ROE_TTM）

增长率统一用 (cur - base) / |base|：
    · 分母取绝对值，亏损转盈时因子为正，方向不会被符号翻转；
    · base 为 0 或缺失时置 NaN；
    · 三年复合要求 cur、base 同为正，否则 NaN。
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def growth(cur: pd.DataFrame, base: pd.DataFrame) -> pd.DataFrame:
    """同比增长率，(cur - base) / |base|。"""
    den = base.abs()
    out = (cur - base) / den.where(den > 1e-9)
    return out.replace([np.inf, -np.inf], np.nan)


def cagr(cur: pd.DataFrame, base: pd.DataFrame, years: int = 3) -> pd.DataFrame:
    """复合增长率，仅在 cur、base 同为正时有定义。"""
    ratio = (cur / base.where(base > 0)).where(cur > 0)
    out = ratio.pow(1.0 / years) - 1.0
    return out.replace([np.inf, -np.inf], np.nan)


def roe_ttm(net_profit_ttm: pd.DataFrame, equity: pd.DataFrame) -> pd.DataFrame:
    """ROE_TTM = 净利润 TTM / 归母净资产（最新财报）。"""
    eq = equity.where(equity > 0)
    return (net_profit_ttm / eq).replace([np.inf, -np.inf], np.nan)


# 平台在部分月份用 0 填充缺失的财务数据（如 000001.SZ 2025-10 起营收为 0），
# 直接参与计算会得到 -100% 的假因子值。统一在因子构建前清洗：
#   营收 <= 0 视为缺失（营收不可能为负，负值多为重组/追溯调整的数据异常）
#   利润、现金流 == 0 视为缺失（负值合法）
#   净资产 <= 0 视为缺失（已资不抵债时 ROE 无意义）
_REVENUE_COLS = ("operating_revenue_mrq", "operating_revenue_ttm")
_ZERO_INVALID_COLS = ("net_profit_mrq", "net_profit_ttm",
                      "net_cffoa_mrq", "net_cffoa_ttm")


def sanitize(w: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """把数据异常值统一转成 NaN，返回副本。"""
    out = dict(w)
    for col in _REVENUE_COLS:
        out[col] = w[col].where(w[col] > 0)
    for col in _ZERO_INVALID_COLS:
        out[col] = w[col].replace(0.0, np.nan)
    eq = "total_equity_to_parent_shareholders"
    out[eq] = w[eq].where(w[eq] > 0)
    return out


def build_factors(w: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """由宽表字典构建 12 个因子，返回 {因子名: 宽表}。

    需要的输入键：
        operating_revenue_mrq / _ttm
        net_profit_mrq / _ttm
        net_cffoa_mrq / _ttm
        total_equity_to_parent_shareholders
    """
    w = sanitize(w)
    out: dict[str, pd.DataFrame] = {}

    for prefix, mrq_col, ttm_col in (
        ("Sales", "operating_revenue_mrq", "operating_revenue_ttm"),
        ("Profit", "net_profit_mrq", "net_profit_ttm"),
        ("OCF", "net_cffoa_mrq", "net_cffoa_ttm"),
    ):
        q, ttm = w[mrq_col], w[ttm_col]
        out[f"{prefix}_G_q"] = growth(q, q.shift(12))
        out[f"{prefix}_G_ttm"] = growth(ttm, ttm.shift(12))
        out[f"{prefix}_G_3y"] = cagr(ttm, ttm.shift(36))

    equity = w["total_equity_to_parent_shareholders"]
    roe_q = roe_ttm(w["net_profit_mrq"], equity)          # 单季 ROE
    roe_ttm_ = roe_ttm(w["net_profit_ttm"], equity)       # TTM ROE

    out["ROE_G_q"] = growth(roe_q, roe_q.shift(12))
    out["ROE_G_ttm"] = growth(roe_ttm_, roe_ttm_.shift(12))
    out["ROE_G_3y"] = cagr(roe_ttm_, roe_ttm_.shift(36))

    return out
