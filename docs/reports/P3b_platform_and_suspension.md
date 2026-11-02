# P3b 报告：平台单文件脚本 + 次日停牌口径

| 项目 | 内容 |
|---|---|
| 报告编号 | P3b-20261102 |
| 日期 | 2026-11-02 |
| 状态 | 已完成 |
| 关联 | P1/P2/P3（口径更新后重跑） |

---

## 0. 摘要

完成两件事：

1. **平台单文件脚本** `platform/bq_factor_lab.py`（470 行），支持 `local` / `dai` 双数据源；
   本地全样本跑通，IC 与 `src/` 结果**逐格一致（max diff = 0）**。
2. **接入"次日停牌"剔除**：按研报"剔除截面期下一交易日停牌"的口径，剔除 341 行（0.08%）；
   P1–P3 全部重跑，IC 最大变化 0.00017、分层 0.00095、回归 t 0.02，结论不变。

---

## 1. 平台脚本

### 1.1 设计

| 项目 | 实现 |
|---|---|
| 依赖 | 仅 pandas / numpy / matplotlib（scipy 不强制） |
| 数据源 | `--source local` 读 `panel_*.csv`；`--source dai` 查 `cn_stock_prefactors` |
| 参数 | `--data-dir --out-dir --start --end --sample --lang` |
| 字体 | 检测 CJK 字体，缺失时自动英文标签 |
| 输出 | `ic_summary.csv`、`ic_series.csv`、`layer_summary.csv`、`regression_summary.csv`、`fdr_summary.csv`、`ls_nav.png` |
| 兼容 | 不使用 pandas 3.x 独有 API（平台为 pandas 2.2 / Python 3.11） |

### 1.2 验证

| 验证 | 方法 | 结果 |
|---|---|---|
| 因子公式一致 | `tests/test_platform_parity.py::test_factor_formula_parity` | 12 因子逐格一致（1e-10） |
| IC 一致 | 同上 `test_ic_parity` | 完全一致 |
| 全样本一致 | 平台脚本跑全样本，与 P2 `ic_mean` 对比 | **max diff = 0.000000** |
| 小样本速度 | 100 只股票 | 约 10 秒 |

### 1.3 平台运行

```bash
# 平台已有数据文件
python platform/bq_factor_lab.py \
  --source local --data-dir /bq_export_v41 --out-dir ./out

# 平台现取
python platform/bq_factor_lab.py --source dai --start 2020-01-01 --end 2025-12-31

# 快速验证
python platform/bq_factor_lab.py \
  --source local --data-dir /bq_export_v41 --sample 100
```

---

## 2. 次日停牌口径

### 2.1 方法

研报原文："剔除每个截面期下一交易日停牌的股票"。

实现（`src/data.py::apply_next_day_suspension`）：

1. 用**停牌事件 + 涨跌停事件 + 月末日期**的并集近似交易日历；
2. 对每个月末 t，取并集中第一个大于 t 的日期作为"下一交易日"；
3. 若该日与 t 相差超过 5 个自然日，视为"下一交易日无停牌事件"，不剔除；
4. 剔除在该日停牌的股票。

**为什么用事件并集而不是完整日历**：只要下一交易日有任意股票停牌，该日必然出现在事件并集里；
若完全没有停牌，则无需剔除。这样不需要额外导出 2,400 行日历。

### 2.2 影响

| 项目 | 数值 |
|---|---|
| 剔除行数 | 341 / 445,724 = **0.08%** |
| 涉及股票 | 5,317 只（数量不变，只是个别月份剔除） |
| 耗时 | 1.6 秒 |

### 2.3 重跑后的变化

| 指标 | 最大绝对变化 |
|---|---|
| IC 均值 | 0.00017 |
| 分层多空收益 | 0.00095 |
| 回归 beta t 值 | 0.020 |
| FDR IC 均值 | 0.00016 |

结论：**所有定性判断不变**，属于"口径补齐"而非"结果改写"。

---

## 3. 测试

`pytest tests -q` → **15 passed**（原 13 个 + 2 个平台一致性）。

---

## 4. 局限

| 局限 | 影响 | 处理 |
|---|---|---|
| 交易日历由事件并集近似 | 极端情况下次日判断可能偏移 | 影响 <0.1%，可接受；如需精确可导出日历 |
| 平台 `dai` 模式未在本地实测 | 只能在平台验证 | 脚本保留，首次平台运行时验证 |
| pandas 2.2 未本地实测 | 版本差异风险 | 代码只用 2.x 通用 API |

---

## 5. 文件

| 文件 | 说明 |
|---|---|
| `platform/bq_factor_lab.py` | 平台单文件流水线 |
| `src/data.py` | 新增 `apply_next_day_suspension` |
| `tests/test_platform_parity.py` | 一致性测试 |
| `output/platform_full/` | 平台脚本全样本输出 |
