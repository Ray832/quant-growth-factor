# -*- coding: utf-8 -*-
"""
BigQuant 指数导出 · 补齐基准（30 秒）
=====================================

用途：v4.1 只探测了 `cn_stock_index_bar1d` 的结构，没有把指数数据导出来。
本脚本导出沪深300（000300.SH）的月频收盘，顺带中证500/中证1000 作为辅助基准。

输出：
    index_000300_monthly.csv   沪深300（主基准）
    index_000905_monthly.csv   中证500（可选）
    index_000852_monthly.csv   中证1000（可选）
    index_probe.csv            平台有哪些指数（排查用）

把生成的 csv 放到 bq_export_v41/ 目录下即可。
"""

import dai
import pandas as pd

START, END = "2016-01-01", "2025-12-31"
SAVE_DIR = "./bq_export_v41"

TARGETS = {
    "000300.SH": "index_000300_monthly.csv",
    "000905.SH": "index_000905_monthly.csv",
    "000852.SH": "index_000852_monthly.csv",
}

# ---------------------------------------------------------------------------
# 1. 先看平台里有哪些指数（万一代码不是 000300.SH）
# ---------------------------------------------------------------------------
try:
    probe = dai.query(
        "SELECT DISTINCT instrument, name FROM cn_stock_index_bar1d "
        "WHERE date = '2025-06-30' LIMIT 500",
        filters={"date": ["2025-06-30"]},
    ).df()
    print(f"平台指数数量（2025-06-30）：{len(probe)}")
    print(probe.head(30).to_string())
    probe.to_csv(f"{SAVE_DIR}/index_probe.csv", index=False, encoding="utf-8-sig")

    hit = probe[probe["instrument"].isin(TARGETS)]
    print("\n目标指数命中：")
    print(hit.to_string() if len(hit) else "（一个都没命中，请看上面的清单换代码）")
except Exception as e:
    print("指数清单查询失败：", type(e).__name__, str(e)[:200])

# ---------------------------------------------------------------------------
# 2. 导出目标指数（日频 → 每月最后一个交易日）
# ---------------------------------------------------------------------------
codes = ", ".join(f"'{c}'" for c in TARGETS)
sql = f"""
SELECT date, instrument, name, close, change_ratio
FROM cn_stock_index_bar1d
WHERE instrument IN ({codes})
  AND date >= '{START}' AND date <= '{END}'
ORDER BY instrument, date
"""

df = dai.query(sql, filters={"date": [START, END]}).df()
df["date"] = pd.to_datetime(df["date"])
print(f"\n日频指数数据：{len(df):,d} 行，{df['instrument'].nunique()} 个指数")

for code, fname in TARGETS.items():
    sub = df[df["instrument"] == code].copy()
    if sub.empty:
        print(f"  {code}: 无数据，跳过")
        continue
    last = sub.groupby(sub["date"].dt.to_period("M"))["date"].max().values
    m = sub[sub["date"].isin(set(last))].sort_values("date")
    m.to_csv(f"{SAVE_DIR}/{fname}", index=False, encoding="utf-8-sig")

    # 年度收益自检
    m["year"] = m["date"].dt.year
    ann = m.groupby("year")["close"].agg(["first", "last"])
    ann["ret"] = (ann["last"] / ann["first"] - 1).round(4)
    print(f"  {code} -> {fname}  {len(m)} 行")
    print("    年度收益:", ann["ret"].to_dict())

print("\n完成。把 index_*.csv 放进 bq_export_v41/ 即可。")
