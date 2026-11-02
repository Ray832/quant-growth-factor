# 数据说明文档

> 项目：量化研报复现 —— 华泰《单因子测试之成长类因子》
> 版本：v1.0　|　数据版本：`bq_export_v41`　|　更新：2026-11-02

---

## 1. 总览

本项目的数据全部来自 **BigQuant 平台**，通过 Python SDK（`import dai`）以 SQL 方式导出，
在本地清洗后固化为 **月频面板 + 指数 + 事件表** 三类文件，总计约 **50 MB**。

```
BigQuant 云端 cn_stock_prefactors（日频 PIT 宽表，6937 列）
        │  SQL 取 33 列，按年拉取
        ▼
本地：日频原始行（每年 70 万–136 万行）
        │  取"每月最后一个交易日"
        ▼
bq_export_v41/panel_YYYY.csv   月频面板（519,860 行 × 33 列）
        │  宽表化 + 滞后对齐
        ▼
12 个成长因子（Sales / Profit / OCF / ROE × q / ttm / 3y）
```

设计原则：

1. **只导必要字段**：6937 列里只取 33 列，避免 GB 级传输；
2. **月频落盘**：回测是月度调仓，日频没必要落盘；
3. **保留原始口径**：不在平台端做任何因子计算，口径全部在本地代码控制；
4. **可复现**：导出脚本、参数、校验结果全部随文档保存。

---

## 2. 数据来源

### 2.1 平台与数据表

| 用途 | 表 | 说明 |
|---|---|---|
| 主数据 | `cn_stock_prefactors` | 日频 PIT 宽表，6,937 列，含行情、市值、财务、行业、状态 |
| 指数 | `cn_stock_index_bar1d` | 指数日线，用于沪深300 / 中证500 / 中证1000 |

访问方式：

```python
import dai
df = dai.query(sql, filters={"date": ["2020-01-01", "2025-12-31"]}).df()
```

`filters` 是分区裁剪参数，必须提供日期区间，否则会要求 `full_db_scan=True`（全表扫描，很慢）。

### 2.2 为什么选 `cn_stock_prefactors`

- **一次拿全**：行情、复权、市值、三大报表、行业、ST/停牌、涨跌停都在同一张表，避免多表 JOIN 的时点错配；
- **已经是 PIT**：财务字段按公告日对齐到每个交易日，直接取用不会产生前视偏差（第 2.4 节有验证）；
- **字段齐全**：每个财务科目都提供"累计 / 单季（`_mrq`）/ TTM（`_ttm`）"三套值，正好对应研报的三个因子族。

### 2.3 关键字段语义

**财务三套口径**（以营业收入为例，已用样本核对数量关系）：

| 字段 | 含义 | 样本值 | 关系 |
|---|---|---|---|
| `operating_revenue` | 年初至今累计 | 3.36 亿 | — |
| `operating_revenue_mrq` | 单季度 | 0.997 亿 | ≈ TTM / 4 |
| `operating_revenue_ttm` | 滚动 12 个月 | 4.57 亿 | > 累计（Q3 时点） |

净利润 `net_profit_*`、经营现金流 `net_cffoa_*` 同名规则。

**行情与市值**：

| 字段 | 含义 | 单位 | 备注 |
|---|---|---|---|
| `close` | 收盘价（**后复权**） | 元 | 已是复权价，可直接算收益 |
| `adjust_factor` | 复权因子 | 倍 | 原始价 = `close / adjust_factor` |
| `upper_limit` / `lower_limit` | 涨跌停价（复权后） | 元 | 与 `close` 同一价格空间 |
| `amount` | 成交额 | 元 | |
| `turn` | 换手率 | 小数 | 0.0226 = 2.26% |
| `total_market_cap` | 总市值 | 元 | 用原始价计算 |
| `float_market_cap` | 流通市值 | 元 | 回归权重用 √流通市值 |
| `total_shares` / `a_float_shares` | 总股本 / 流通股本 | 股 | |
| `daily_return` | 当日收益率 | 小数 | 0.0195 = 1.95% |

**状态与分类**：

| 字段 | 含义 | 取值 |
|---|---|---|
| `st_status` | ST 状态 | 0 = 正常；>0 = ST/*ST |
| `is_risk_warning` | 风险警示 | 0/1 |
| `suspended` | 停牌 | 0 = 正常交易；1 = 停牌 |
| `price_limit_status` | 涨跌停状态 | **1=涨停、2=正常、3=跌停** |
| `list_date` / `list_days` | 上市日 / 已上市天数 | — |
| `sw2021_level1` / `_name` | 申万2021 一级行业 | 代码（480000）/ 名称（银行） |
| `is_bj` / `is_kcb` / `is_cyb` | 北交所 / 科创板 / 创业板 | 0/1 |

> `price_limit_status` 是最容易误解的字段：它 97% 的行都是 2（正常），
> 按"非 0"过滤会得到 1000 万行无效数据。正确用法是 `IN (1, 3)`。

### 2.4 PIT（时点）机制与验证

平台把财务数据按**公告日**对齐到交易日：某公司 4 月 21 日披露一季报，则 4 月 21 日之前的所有交易日都只能看到上一期财报。

验证方法：取 5 只股票的日频财务序列，找出 `net_profit_ttm` 发生变化的日期。

| 股票 | 财务值变动日 | 解读 |
|---|---|---|
| 平安银行 000001.SZ | 03-10、04-21、10-21 | 银行年报 3 月、一季报 4 月下旬、三季报 10 月下旬 |
| 格力电器 000651.SZ | 10-31、08-31、04-29 | 正好是披露截止日 |

变动日不是整齐的 3/31、6/30、9/30，而是各公司真实公告日 → **确认无前视偏差**。

---

## 3. 数据获取

### 3.1 导出脚本

| 脚本 | 用途 |
|---|---|
| `export/bigquant_export_v41.py` | 主脚本：月频面板 + 停牌/涨跌停事件 + PIT 样本 |
| `export/bigquant_export_index.py` | 指数：沪深300 / 中证500 / 中证1000 月频 |

运行环境：BigQuant BigStudio，Python 3.11，`import dai` 可用（平台已注入凭证，无需配置 AK/SK）。

### 3.2 查询逻辑

```sql
SELECT <33 列>
FROM cn_stock_prefactors
WHERE date >= '2016-01-01' AND date <= '2025-12-31'
```

按年循环，共 10 次查询：

- 每年约 70 万–136 万行；
- 用 `filters={"date": [当年起, 当年止]}` 做分区裁剪；
- 不在 SQL 里剔除 ST/停牌，而是把标记一起导出，把"是否剔除"的决定留给回测阶段。

### 3.3 月频压缩

每年数据拿到后，在平台端立刻压成月频：

```python
days = pd.Series(df["date"].unique())
month_end = days.groupby(days.dt.to_period("M")).max()   # 每月最后一个交易日
snap = df[df["date"].isin(set(month_end.values))]
```

- 用"全市场交易日"确定月末，而不是每只股票自己的最后一天，避免停牌股错位；
- 压缩比约 20:1（2025 年 136 万行 → 6.7 万行）；
- 落盘后立即释放日频数据，平台内存压力小。

**为什么用月频**：研报是"每月末核算因子、下月初调仓"，月度截面已经包含回测所需的全部信息。

### 3.4 辅助表

| 表 | 查询 | 用途 |
|---|---|---|
| `suspension_events.csv` | `WHERE suspended = 1` | 判断"调仓日次日是否停牌" |
| `limit_events_valid.csv` | `WHERE price_limit_status IN (1,3)` | 涨跌停可交易性检验 |
| `daily_fin_sample.csv` | 5 只股票日频财务 | PIT 验证 |

事件表采用"稀疏存储"：只存发生事件的记录，而不是每天每只股票一行。

### 3.5 指数

```sql
SELECT date, instrument, name, close, change_ratio
FROM cn_stock_index_bar1d
WHERE instrument = '000300.SH'
  AND date >= '2016-01-01' AND date <= '2025-12-31'
```

同样取每月最后一个交易日。已导出沪深300、中证500、中证1000 三个基准。

### 3.6 复现步骤

1. 在 BigStudio 运行 `bigquant_export_v41.py`，产出 `bq_export_v41/`；
2. 运行 `bigquant_export_index.py`，把 `index_*.csv` 放进同一目录；
3. 本地 `pytest tests -q` 验证；
4. 若平台数据更新，改脚本里的 `START_YEAR / END_YEAR` 重跑即可。

---

## 4. 获取结果

### 4.1 文件清单

| 文件 | 大小 | 行数 | 内容 |
|---|---|---|---|
| `panel_2016.csv` … `panel_2025.csv` | 12–25 MB/年 | 合计 519,860 | 月频面板，33 列 |
| `index_000300_monthly.csv` | 7 KB | 120 | 沪深300 月频 |
| `index_000905_monthly.csv` | 7 KB | 120 | 中证500 月频 |
| `index_000852_monthly.csv` | 7 KB | 120 | 中证1000 月频 |
| `suspension_events.csv` | 3.7 MB | 185,594 | 停牌事件 |
| `limit_events_valid.csv` | 5.3 MB | 229,635 | 涨跌停事件（涨停 70,826 / 跌停 158,809） |
| `daily_fin_sample.csv` | 1.0 MB | 12,150 | 5 只股票日频财务 |
| `meta.json` / `export_log.txt` | — | — | 导出参数与日志 |

### 4.2 覆盖统计

| 年份 | 月频行数 | 全年股票数 | 剔除北交所后 | ST 记录 |
|---|---|---|---|---|
| 2016 | 34,726 | 3,035 | 3,035 | 778 |
| 2017 | 39,452 | 3,471 | 3,471 | 850 |
| 2018 | 42,356 | 3,572 | 3,572 | 989 |
| 2019 | 43,871 | 3,770 | 3,770 | 1,498 |
| 2020 | 47,172 | 4,155 | 4,155 | 2,295 |
| 2021 | 52,964 | 4,783 | 4,622 | 2,345 |
| 2022 | 59,649 | 5,274 | 4,947 | 1,882 |
| 2023 | 65,090 | 5,619 | 5,141 | 1,548 |
| 2024 | 67,289 | 5,681 | 5,171 | 1,564 |
| 2025 | 67,291 | 5,747 | 5,211 | 2,006 |

评估期 **2020-01 ~ 2025-12**，共 72 个截面，每期约 3,600–5,200 只。

### 4.3 质量校验

| 校验项 | 结果 | 结论 |
|---|---|---|
| 主键重复 | `(date, instrument)` 重复 0 行 | 通过 |
| 截面完整 | 120 个月，每年 12 个 | 通过 |
| 退市股 | 乐视退 / 暴风退 / 退市锐电 3/3 在库 | 无生存偏差 |
| 行业覆盖 | 2017 年 99.9%，2025 年 95.7% | 缺口与停牌股重合 |
| 复权链 | 平安银行 2024 年 +35.41%（真实约 +35%） | 通过 |
| 收益分布 | 月均 +0.94%，标准差 14.16% | 合理 |
| PIT | 财务值变动日 = 公告日 | 通过 |

---

## 5. 存储结构

### 5.1 目录

```
E:\量化研报复现\
├─ bq_export_v41\            数据（50 MB，只读）
│   ├─ panel_2016.csv … panel_2025.csv
│   ├─ index_000300_monthly.csv  index_000905_monthly.csv  index_000852_monthly.csv
│   ├─ suspension_events.csv  limit_events_valid.csv  daily_fin_sample.csv
│   └─ meta.json  export_log.txt
├─ src\                      代码
│   ├─ config.py             路径、股票池规则、因子清单
│   ├─ data.py               加载、过滤、宽表转换
│   ├─ factors.py            12 个因子
│   ├─ preprocess.py         去极值、标准化、行业中性
│   └─ evaluate.py           前瞻收益、IC、分层、绩效
├─ tests\                    测试
│   ├─ conftest.py           小样本 fixture
│   └─ test_smoke.py         11 个端到端用例
├─ scripts\smoke_report.py   小样本演示
├─ docs\                     文档
└─ output\                   结果输出
```

### 5.2 `panel_YYYY.csv` 字段字典

主键：`(date, instrument)`；排序：`date, instrument`；编码：UTF-8（带 BOM）。

| 字段 | 类型 | 单位 | 含义 | 空值率* |
|---|---|---|---|---|
| `date` | date | — | 月末交易日 | 0% |
| `instrument` | str | — | 代码，`000001.SZ` | 0% |
| `name` | str | — | 证券简称 | 3.3% |
| `list_date` | date | — | 上市日 | 3.3% |
| `list_days` | int | 天 | 已上市天数 | 3.3% |
| `close` | float | 元 | **后复权**收盘价 | 3.4% |
| `adjust_factor` | float | 倍 | 复权因子 | 3.3% |
| `daily_return` | float | 小数 | 当日收益率 | 3.4% |
| `total_market_cap` | float | 元 | 总市值 | 3.3% |
| `float_market_cap` | float | 元 | 流通市值 | 3.3% |
| `total_shares` | float | 股 | 总股本 | 3.3% |
| `a_float_shares` | float | 股 | 流通股本 | 3.3% |
| `amount` | float | 元 | 成交额 | 3.4% |
| `turn` | float | 小数 | 换手率 | 3.3% |
| `operating_revenue_mrq` | float | 元 | 单季营业收入 | 3.3% |
| `operating_revenue_ttm` | float | 元 | TTM 营业收入 | 3.3% |
| `net_profit_mrq` | float | 元 | 单季归母净利润 | 3.3% |
| `net_profit_ttm` | float | 元 | TTM 归母净利润 | 3.3% |
| `net_cffoa_mrq` | float | 元 | 单季经营现金流净额 | 3.3% |
| `net_cffoa_ttm` | float | 元 | TTM 经营现金流净额 | 3.3% |
| `total_equity_to_parent_shareholders` | float | 元 | 归母净资产 | 3.3% |
| `roe_avg_ttm` | float | 小数 | 平台口径 ROE（交叉验证用） | 3.3% |
| `st_status` | int | — | ST 状态 | 3.3% |
| `is_risk_warning` | int | — | 风险警示 | 3.3% |
| `suspended` | int | — | 停牌 | 3.3% |
| `upper_limit` | float | 元 | 涨停价 | 3.3% |
| `lower_limit` | float | 元 | 跌停价 | 3.3% |
| `price_limit_status` | int | — | 1 涨停 / 2 正常 / 3 跌停 | 3.3% |
| `sw2021_level1` | float | — | 申万一级行业代码 | 3.3% |
| `sw2021_level1_name` | str | — | 申万一级行业名称 | 3.3% |
| `is_bj` / `is_kcb` / `is_cyb` | int | — | 板块标记 | 0% |

\* 空值率取自 2025 年截面；空值主要由停牌、退市、未上市造成。

### 5.3 指数文件

| 字段 | 类型 | 说明 |
|---|---|---|
| `date` | date | 月末交易日 |
| `instrument` | str | `000300.SH` 等 |
| `name` | str | 指数名称 |
| `close` | float | 收盘点位 |
| `change_ratio` | float | 当日涨跌幅 |

### 5.4 事件文件

| 文件 | 字段 | 说明 |
|---|---|---|
| `suspension_events.csv` | `date, instrument` | 只保留 `suspended = 1` 的记录 |
| `limit_events_valid.csv` | `date, instrument, price_limit_status` | 只保留 1（涨停）/ 3（跌停） |

### 5.5 约定

- **日期**：`YYYY-MM-DD`，月末交易日；
- **代码**：`6位数字.交易所`，如 `000001.SZ`、`600519.SH`；
- **金额**：一律为**元**，不是万元；
- **比率**：一律为**小数**（0.0226），不是百分数（2.26）；
- **缺失**：留空，不填 0；
- **编码**：UTF-8 带 BOM，Excel 可直接打开。

### 5.6 派生数据

| 派生项 | 计算方式 | 代码位置 |
|---|---|---|
| 月收益率 | `close.pct_change()`（后复权） | `src/evaluate.forward_return` |
| 12 个因子 | 见 `src/factors.py` | 同左 |
| 去极值/标准化 | 中位数 ±5×MAD、z-score | `src/preprocess.py` |

---

## 6. 已知问题与处理

| 问题 | 现象 | 处理 |
|---|---|---|
| 北交所断档 | 2025-10 起北交所无数据（242 只） | 全样本剔除 `is_bj = 1` |
| 涨跌停表膨胀 | `price_limit_status != 0` 含 97% 正常行 | 改为 `IN (1,3)`，226 MB → 5.3 MB |
| 次新股极端收益 | 633 条月收益 > 100% | 入池要求 `list_days >= 365` + 5×MAD |
| 停牌股缺价 | `close` 缺失 3.4% | 调仓日剔除，次日停牌用事件表补判 |
| 财务负基数 | 亏损公司同比无意义 | 分母取绝对值；三年复合要求同为正 |
| **财务 0 填充** | 部分股票某月营收/净利为 0（如 000001.SZ 2025-10 起），会算出 -100% 的假因子 | 因子构建前：营收 `<=0`、利润/现金流 `==0`、净资产 `<=0` 一律视为缺失 |

---

## 7. 使用方式

### 7.1 环境

```powershell
& 'E:\量化研报复现\env.cmd' -c "import pandas; print(pandas.__version__)"
& 'E:\量化研报复现\env.cmd' -m pytest tests -q
```

### 7.2 标准流程

```python
from src import data, factors, preprocess, evaluate

raw  = data.load_panel()                 # 读 10 个面板文件
pool = data.filter_pool(raw)             # 剔北交所/ST/停牌/次新
wide = data.to_wide(pool)                # 转宽表
ind  = wide["sw2021_level1_name"]        # 行业

fac = {k: preprocess.process(v, industry=ind)
       for k, v in factors.build_factors(wide).items()}

fwd = evaluate.forward_return(wide["close"])
ic  = evaluate.ic_series(fac["Profit_G_q"], fwd)
lay = evaluate.layer_returns(fac["Profit_G_q"], fwd, ind, n=5)
```

### 7.3 常见错误

| 报错 | 原因 |
|---|---|
| `FileNotFoundError: bq_export_v41` | 数据目录被移动，改 `src/config.py` 的 `DATA_DIR` |
| `KeyError: 'sw2021_level1_name'` | `load_panel` 的 `columns` 参数漏了该列 |
| IC 全是 NaN | 因子与收益的日期索引没对齐，检查 `fwd` 是否用同一 `close` 宽表 |

---

## 8. 维护

- **数据更新**：改 `export/bigquant_export_v41.py` 的 `START_YEAR / END_YEAR`，重跑后覆盖目录；
- **字段变更**：平台若改字段名，只需改 `src/config.py` 的 `PANEL_COLS` 与 `src/factors.py` 的映射；
- **版本记录**：

| 版本 | 日期 | 变更 |
|---|---|---|
| v1.0 | 2026-11-02 | 首次导出：2016–2025 月频、三角指数、事件表、PIT 样本 |
