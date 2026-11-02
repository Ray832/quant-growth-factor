"""项目级配置：路径、股票池规则、因子定义。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "bq_export_v41"
OUT_DIR = ROOT / "output"

# ---- 股票池规则 -----------------------------------------------------------
MIN_LIST_DAYS = 365        # 上市满 12 个月
EXCLUDE_BJ = True          # 剔除北交所
EXCLUDE_ST = True          # 剔除 ST
EXCLUDE_SUSPENDED = True   # 剔除调仓日停牌

# ---- 因子处理 -------------------------------------------------------------
MAD_K = 5.0                # 中位数 ±5×MAD
N_LAYERS = 5               # 分层数

# ---- 评估期 ---------------------------------------------------------------
EVAL_START = "2020-01-01"
EVAL_END = "2025-12-31"

# ---- 因子清单 -------------------------------------------------------------
FACTORS = [
    "Sales_G_q", "Sales_G_ttm", "Sales_G_3y",
    "Profit_G_q", "Profit_G_ttm", "Profit_G_3y",
    "OCF_G_q", "OCF_G_ttm", "OCF_G_3y",
    "ROE_G_q", "ROE_G_ttm", "ROE_G_3y",
]

# 月频面板中需要用到的列（其余列不读，降低内存）
PANEL_COLS = [
    "date", "instrument", "close", "float_market_cap", "total_market_cap",
    "st_status", "suspended", "list_days", "is_bj", "sw2021_level1_name",
    "operating_revenue_mrq", "operating_revenue_ttm",
    "net_profit_mrq", "net_profit_ttm",
    "net_cffoa_mrq", "net_cffoa_ttm",
    "total_equity_to_parent_shareholders", "roe_avg_ttm",
]
