# -*- coding: utf-8 -*-
"""
BigQuant 正式导出 v4.1 · 月度面板 2016–2025（评估期 2020–2025）
================================================================

按确认口径调整：
    · 样本期：导出 2016-01 ~ 2025-12；评估期 2020-01 ~ 2025-12
      （多导 3 年是为了三年复合增长率因子在 2020 年初有值）
    · 基准/行业权重：降级为全 A 流通市值口径，不导沪深300 成分
    · 不做估值因子对比：不导 pb / pe_ttm / ps_ttm
    · 当季因子用单季口径（_mrq）
    · 补三张辅助表：停牌事件、涨跌停事件、日频财务样本（PIT 验证）

输出 ./bq_export_v41/
    panel_2016.csv ... panel_2025.csv    月频面板（每月最后一个交易日）
    suspension_events.csv                停牌事件（稀疏）
    limit_events.csv                     涨跌停事件（稀疏）
    daily_fin_sample.csv                 5 只股票日频财务（验证 PIT）
    index_000300.csv                     沪深300 月频（若能找到）
    meta.json / export_log.txt

预计：21 次年度查询 → 10 分钟以内；总体积 < 100 MB。
"""

from __future__ import annotations

import os
import json
import traceback
from datetime import datetime

import numpy as np
import pandas as pd

SAVE_DIR = "./bq_export_v41"
os.makedirs(SAVE_DIR, exist_ok=True)

START_YEAR = 2016
END_YEAR = 2025

# 月频面板字段（33 列）
FIELDS = [
    "date", "instrument", "name", "list_date", "list_days",
    "close", "adjust_factor", "daily_return",
    "total_market_cap", "float_market_cap",
    "total_shares", "a_float_shares", "amount", "turn",
    "operating_revenue_mrq", "operating_revenue_ttm",
    "net_profit_mrq", "net_profit_ttm",
    "net_cffoa_mrq", "net_cffoa_ttm",
    "total_equity_to_parent_shareholders", "roe_avg_ttm",
    "st_status", "is_risk_warning", "suspended",
    "upper_limit", "lower_limit", "price_limit_status",
    "sw2021_level1", "sw2021_level1_name",
    "is_bj", "is_kcb", "is_cyb",
]

PIT_SAMPLE_STOCKS = ["000001.SZ", "600519.SH", "000651.SZ", "600036.SH", "002415.SZ"]

LOG = []


def log(*a):
    m = " ".join(str(x) for x in a)
    print(m)
    LOG.append(m)


def q(dai, sql, filters=None, **kw):
    if filters is not None:
        try:
            return dai.query(sql, filters=filters, **kw).df()
        except TypeError:
            pass
    return dai.query(sql, **kw).df()


# ---------------------------------------------------------------------------
# STEP 1 预检
# ---------------------------------------------------------------------------

def preflight(dai):
    log("=" * 78)
    log(f"STEP 1 预检   {datetime.now():%Y-%m-%d %H:%M:%S}")
    log("=" * 78)

    coverage = []
    for y in range(START_YEAR, END_YEAR + 1):
        try:
            df = q(dai,
                   "SELECT count(*) AS rows, uniqExact(instrument) AS n_inst "
                   "FROM cn_stock_prefactors "
                   f"WHERE date >= '{y}-01-01' AND date <= '{y}-12-31'",
                   filters={"date": [f"{y}-01-01", f"{y}-12-31"]})
            r, n = int(df.iloc[0, 0]), int(df.iloc[0, 1])
        except Exception as e:
            r, n = -1, -1
            log(f"  {y}: 查询失败 {type(e).__name__}: {str(e)[:80]}")
        coverage.append({"year": y, "rows": r, "instruments": n})
        log(f"  {y}: rows={r:>10,d}  instruments={n:>5,d}")

    for d in ("2017-06-30", "2020-06-30", "2023-06-30", "2025-06-30"):
        try:
            df = q(dai,
                   "SELECT count(*) AS n_all, count(sw2021_level1) AS n_ind, "
                   "count(total_market_cap) AS n_mv, count(net_cffoa_ttm) AS n_cfo "
                   f"FROM cn_stock_prefactors WHERE date = '{d}'",
                   filters={"date": [d]})
            log(f"  {d}: 股票={int(df.iloc[0,0])} 行业={int(df.iloc[0,1])} "
                f"市值={int(df.iloc[0,2])} 现金流TTM={int(df.iloc[0,3])}")
        except Exception as e:
            log(f"  {d}: 失败 {type(e).__name__}: {str(e)[:80]}")

    # 退市股抽查（2020 后退市的典型：乐视退 300104、暴风退 300431、退市锐电 601558）
    try:
        df = q(dai,
               "SELECT count(*) AS n FROM cn_stock_prefactors "
               "WHERE date = '2019-06-28' "
               "AND instrument IN ('300104.SZ','300431.SZ','601558.SH')",
               filters={"date": ["2019-06-28"]})
        log(f"  退市股抽查(2019-06-28): 命中 {int(df.iloc[0,0])} / 3")
    except Exception as e:
        log(f"  退市股抽查失败: {type(e).__name__}: {str(e)[:80]}")

    # 板块分布
    try:
        df = q(dai,
               "SELECT sum(is_bj) AS bj, sum(is_kcb) AS kcb, sum(is_cyb) AS cyb, "
               "count(*) AS n FROM cn_stock_prefactors WHERE date = '2025-06-30'",
               filters={"date": ["2025-06-30"]})
        log(f"  2025-06-30 板块: 北交所={int(df.iloc[0,0] or 0)} "
            f"科创板={int(df.iloc[0,1] or 0)} 创业板={int(df.iloc[0,2] or 0)} "
            f"合计={int(df.iloc[0,3])}")
    except Exception as e:
        log(f"  板块统计失败: {type(e).__name__}: {str(e)[:80]}")

    index_tables = {}
    for t in ("cn_index_bar1d", "cn_index_prefactors", "cn_stock_index_bar1d",
              "cn_index_daily", "cn_stock_index_weights", "cn_index_weights"):
        try:
            d = q(dai, f"DESCRIBE {t}")
            index_tables[t] = d.shape[0]
            log(f"  [OK] 指数候选表 {t}: {d.shape[0]} 列")
        except Exception:
            log(f"  [--] {t} 不存在")

    return {"coverage": coverage, "index_tables": index_tables}


# ---------------------------------------------------------------------------
# STEP 2 月频面板
# ---------------------------------------------------------------------------

def export_year(dai, y):
    sql = (f"SELECT {', '.join(FIELDS)} FROM cn_stock_prefactors "
           f"WHERE date >= '{y}-01-01' AND date <= '{y}-12-31'")
    df = q(dai, sql, filters={"date": [f"{y}-01-01", f"{y}-12-31"]})
    if df is None or df.empty:
        log(f"  {y}: 空")
        return 0

    df["date"] = pd.to_datetime(df["date"])
    days = pd.Series(df["date"].unique())
    month_end = days.groupby(days.dt.to_period("M")).max()
    snap = df[df["date"].isin(set(month_end.values))].copy()
    snap = snap.sort_values(["date", "instrument"]).reset_index(drop=True)

    out = os.path.join(SAVE_DIR, f"panel_{y}.csv")
    snap.to_csv(out, index=False, encoding="utf-8-sig")
    log(f"  {y}: 日频 {len(df):>9,d} -> 月频 {len(snap):>7,d} 行")
    return len(snap)


# ---------------------------------------------------------------------------
# STEP 3 辅助表
# ---------------------------------------------------------------------------

def export_events(dai):
    log("\n" + "-" * 78)
    log("STEP 3 稀疏事件表")
    log("-" * 78)

    # 停牌事件
    frames = []
    for y in range(START_YEAR, END_YEAR + 1):
        try:
            d = q(dai,
                  "SELECT date, instrument FROM cn_stock_prefactors "
                  f"WHERE suspended = 1 AND date >= '{y}-01-01' AND date <= '{y}-12-31'",
                  filters={"date": [f"{y}-01-01", f"{y}-12-31"]})
            frames.append(d)
        except Exception as e:
            log(f"  停牌 {y}: {type(e).__name__}: {str(e)[:80]}")
    if frames:
        ev = pd.concat(frames, ignore_index=True).drop_duplicates()
        ev.to_csv(os.path.join(SAVE_DIR, "suspension_events.csv"),
                  index=False, encoding="utf-8-sig")
        log(f"  停牌事件: {len(ev):,d} 行")

    # 涨跌停事件
    frames = []
    for y in range(START_YEAR, END_YEAR + 1):
        try:
            d = q(dai,
                  "SELECT date, instrument, price_limit_status FROM cn_stock_prefactors "
                  f"WHERE price_limit_status != 0 "
                  f"AND date >= '{y}-01-01' AND date <= '{y}-12-31'",
                  filters={"date": [f"{y}-01-01", f"{y}-12-31"]})
            frames.append(d)
        except Exception as e:
            log(f"  涨跌停 {y}: {type(e).__name__}: {str(e)[:80]}")
    if frames:
        ev = pd.concat(frames, ignore_index=True).drop_duplicates()
        ev.to_csv(os.path.join(SAVE_DIR, "limit_events.csv"),
                  index=False, encoding="utf-8-sig")
        log(f"  涨跌停事件: {len(ev):,d} 行")


def export_pit_sample(dai):
    log("\n" + "-" * 78)
    log("STEP 3b 日频财务样本（PIT 验证）")
    log("-" * 78)

    quoted = ", ".join(f"'{x}'" for x in PIT_SAMPLE_STOCKS)
    sql = ("SELECT date, instrument, operating_revenue_ttm, net_profit_ttm, "
           "net_cffoa_ttm, total_equity_to_parent_shareholders "
           "FROM cn_stock_prefactors "
           f"WHERE instrument IN ({quoted}) "
           f"AND date >= '{START_YEAR}-01-01' AND date <= '{END_YEAR}-12-31' "
           "ORDER BY instrument, date")
    try:
        df = q(dai, sql, filters={"date": [f"{START_YEAR}-01-01", f"{END_YEAR}-12-31"]})
        df.to_csv(os.path.join(SAVE_DIR, "daily_fin_sample.csv"),
                  index=False, encoding="utf-8-sig")
        log(f"  日频财务样本: {len(df):,d} 行（{len(PIT_SAMPLE_STOCKS)} 只股票）")
    except Exception:
        log(traceback.format_exc())


# ---------------------------------------------------------------------------
# STEP 4 指数
# ---------------------------------------------------------------------------

def export_index(dai, index_tables):
    log("\n" + "-" * 78)
    log("STEP 4 指数")
    log("-" * 78)

    for t in ("cn_index_bar1d", "cn_index_prefactors", "cn_stock_index_bar1d"):
        if t not in index_tables:
            continue
        try:
            df = q(dai, f"SELECT * FROM {t} WHERE date = '2024-01-02' LIMIT 5",
                   filters={"date": ["2024-01-02"]})
            log(f"[OK] {t} 列: {list(df.columns)[:20]}")
            log(df.head(3).to_string()[:600])
        except Exception as e:
            log(f"[--] {t}: {type(e).__name__}: {str(e)[:100]}")


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main():
    import dai

    log(f"BigQuant 导出 v4.1   {datetime.now():%Y-%m-%d %H:%M:%S}")
    log(f"导出区间 {START_YEAR}–{END_YEAR}  评估期 2020–2025  字段 {len(FIELDS)} 个")

    meta = preflight(dai)

    log("\n" + "-" * 78)
    log("STEP 2 月频面板")
    log("-" * 78)
    total = 0
    for y in range(START_YEAR, END_YEAR + 1):
        try:
            total += export_year(dai, y)
        except Exception:
            log(f"  {y}: 失败\n{traceback.format_exc()}")
    log(f"\n月频面板合计: {total:,d} 行")

    export_events(dai)
    export_pit_sample(dai)
    export_index(dai, meta["index_tables"])

    meta.update({"fields": FIELDS, "total_rows": total,
                 "eval_start": "2020-01-01", "eval_end": f"{END_YEAR}-12-31"})
    with open(os.path.join(SAVE_DIR, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2, default=str)
    with open(os.path.join(SAVE_DIR, "export_log.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(LOG))

    log("\n" + "=" * 78)
    log("完成。把 bq_export_v41/ 整个目录打包发回。")
    log("=" * 78)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log(traceback.format_exc())
        with open(os.path.join(SAVE_DIR, "export_log.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(LOG))
