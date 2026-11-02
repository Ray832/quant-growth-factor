"""pytest 公共 fixture：小样本数据集（80 只股票 × 2020–2025）。"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import config, data, evaluate, factors, preprocess  # noqa: E402

N_STOCKS = 80
EVAL_START = "2020-01-01"


@pytest.fixture(scope="session")
def sample():
    """构建一次，全测试复用。"""
    raw = data.load_panel()
    pool = data.filter_pool(raw)

    # 选 2020 年后数据最完整的 80 只，保证小样本也有足够截面
    recent = pool[pool["date"] >= EVAL_START]
    top = (recent.groupby("instrument")["close"].count()
           .sort_values(ascending=False).head(N_STOCKS).index)
    sub = pool[pool["instrument"].isin(top)].copy()

    wide = data.to_wide(sub)
    ind = wide["sw2021_level1_name"]

    fac_raw = factors.build_factors(wide)
    fac = {k: preprocess.process(v, industry=ind) for k, v in fac_raw.items()}

    fwd = evaluate.forward_return(wide["close"])

    # 评估期切片
    dates = [d for d in wide["close"].index if d >= pd.Timestamp(EVAL_START)]
    fac = {k: v.loc[dates] for k, v in fac.items()}
    fwd = fwd.loc[dates]
    ind = ind.loc[dates]

    return {
        "raw": raw,
        "pool": pool,
        "sub": sub,
        "wide": wide,
        "industry": ind,
        "factors_raw": {k: v.loc[dates] for k, v in fac_raw.items()},
        "factors": fac,
        "fwd": fwd,
        "dates": dates,
    }
