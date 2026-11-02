"""数据加载与宽表转换。

月频面板 → (date × instrument) 宽表，是所有因子计算的统一输入格式。
"""

from __future__ import annotations

import pandas as pd

from . import config


def load_panel(years=None, columns=None) -> pd.DataFrame:
    """读取月频面板。

    Parameters
    ----------
    years : iterable[int] | None
        只读指定年份，None 表示全部。
    columns : list[str] | None
        只读指定列，None 表示 PANEL_COLS。
    """
    cols = list(columns or config.PANEL_COLS)
    if "date" not in cols:
        cols.append("date")

    files = sorted(config.DATA_DIR.glob("panel_*.csv"))
    if years is not None:
        wanted = {int(y) for y in years}
        files = [f for f in files if int(f.stem.split("_")[1]) in wanted]
    if not files:
        raise FileNotFoundError(f"没有找到月频面板: {config.DATA_DIR}")

    frames = [pd.read_csv(f, usecols=cols, parse_dates=["date"]) for f in files]
    df = pd.concat(frames, ignore_index=True)
    return df.sort_values(["date", "instrument"]).reset_index(drop=True)


def filter_pool(df: pd.DataFrame, min_list_days: int | None = None) -> pd.DataFrame:
    """按研报口径过滤股票池（不含因子缺失过滤）。"""
    min_days = config.MIN_LIST_DAYS if min_list_days is None else min_list_days
    mask = pd.Series(True, index=df.index)
    if config.EXCLUDE_BJ:
        mask &= df["is_bj"].fillna(0).eq(0)
    if config.EXCLUDE_ST:
        mask &= df["st_status"].fillna(0).le(0)
    if config.EXCLUDE_SUSPENDED:
        mask &= df["suspended"].fillna(0).eq(0)
    mask &= df["list_days"].fillna(0) >= min_days
    return df[mask].copy()


def pivot(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """长表 → 宽表（index=date, columns=instrument）。"""
    wide = df.pivot(index="date", columns="instrument", values=column)
    return wide.sort_index().sort_index(axis=1)


def to_wide(df: pd.DataFrame, columns=None) -> dict[str, pd.DataFrame]:
    """一次性把多列转成宽表，返回 {列名: 宽表}。"""
    cols = columns or [c for c in df.columns if c not in ("date", "instrument")]
    return {c: pivot(df, c) for c in cols}


def load_index(code: str = "000300") -> pd.DataFrame:
    """读取指数月频（date, close）。"""
    path = config.DATA_DIR / f"index_{code}_monthly.csv"
    df = pd.read_csv(path, parse_dates=["date"])
    return df.sort_values("date").reset_index(drop=True)


def load_suspension() -> pd.DataFrame:
    """停牌事件（date, instrument）。"""
    path = config.DATA_DIR / "suspension_events.csv"
    return pd.read_csv(path, parse_dates=["date"])


def _calendar_hint() -> pd.DatetimeIndex:
    """用停牌/涨跌停事件的日期并集近似交易日历。

    事件覆盖了大量交易日；某日若有股票停牌或涨跌停，该日必然在并集中。
    对"判断次日是否停牌"来说，只要次日有任意股票停牌，该日就能被识别。
    """
    parts = [load_suspension()["date"]]
    limit_path = config.DATA_DIR / "limit_events_valid.csv"
    if limit_path.exists():
        parts.append(pd.read_csv(limit_path, usecols=["date"], parse_dates=["date"])["date"])
    for f in sorted(config.DATA_DIR.glob("panel_*.csv")):
        parts.append(pd.read_csv(f, usecols=["date"], parse_dates=["date"])["date"])
    return pd.DatetimeIndex(sorted(set(pd.concat(parts).unique())))


def apply_next_day_suspension(pool: pd.DataFrame, max_gap_days: int = 5) -> pd.DataFrame:
    """剔除"截面期下一交易日停牌"的股票（研报口径）。

    次日由事件日期并集推断：若某日是下一交易日且当天有股票停牌，该日必在并集中。
    若下一交易日没有任何停牌，则无需剔除。
    """
    susp = load_suspension()
    by_date = susp.groupby("date")["instrument"].apply(set).to_dict()
    cal = _calendar_hint()
    dates = pd.DatetimeIndex(sorted(pool["date"].unique()))

    drop = set()
    for d in dates:
        later = cal[cal > d]
        if len(later) == 0:
            continue
        nd = later[0]
        if (nd - d).days > max_gap_days:
            continue
        for inst in by_date.get(nd, ()):  # 次日无停牌时为空集，不会误删
            drop.add((d, inst))

    if not drop:
        return pool
    keys = pd.Series(list(zip(pool["date"], pool["instrument"])), index=pool.index)
    return pool[~keys.isin(drop)]
