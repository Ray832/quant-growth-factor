"""平台单文件版与本地 src 的一致性测试（防止两套代码漂移）。"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def _load_lab():
    path = ROOT / "platform" / "bq_factor_lab.py"
    spec = importlib.util.spec_from_file_location("bq_factor_lab", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_factor_formula_parity(sample):
    """同一份宽表，平台版与 src 的 12 个因子必须逐格一致。"""
    from src import factors

    lab = _load_lab()
    w = sample["wide"]

    a = factors.build_factors(w)
    b = lab.build_factors(w)

    assert set(a) == set(b)
    for k in a:
        np.testing.assert_allclose(
            a[k].to_numpy(), b[k].to_numpy(), rtol=1e-10, atol=1e-12, equal_nan=True,
            err_msg=f"{k} 不一致",
        )


def test_ic_parity(sample):
    """同一份因子与收益，平台版与 src 的 IC 序列必须一致。"""
    from src import evaluate

    lab = _load_lab()
    f = sample["factors"]["Profit_G_q"]
    fwd = sample["fwd"]

    a = evaluate.ic_series(f, fwd)
    b = lab.ic_series(f, fwd)

    np.testing.assert_allclose(a.to_numpy(), b.to_numpy(), rtol=1e-10, atol=1e-12)
