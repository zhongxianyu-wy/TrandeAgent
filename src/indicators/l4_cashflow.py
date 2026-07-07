"""L4 现金流指标（T09 + T10）。

- T09：份额同比变动 + 机构持有比例变化
- T10：历史分红统计

DataProvider 标准接口不直接提供份额/机构持有/分红数据，
因此本模块接受补充参数；缺失时各字段默认 0。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.indicators.models import L4Cashflow


def calc_share_change_yoy(shares_series: pd.Series | dict | None) -> float:
    """份额同比变动。

    Args:
        shares_series: 按时间排序的份额序列（dict[date->share] 或 Series）。

    Returns:
        (最新 - 一年前) / 一年前。数据不足返回 0.0。
    """
    if shares_series is None:
        return 0.0
    if isinstance(shares_series, dict):
        if len(shares_series) < 2:
            return 0.0
        items = sorted(shares_series.items())
        latest = float(items[-1][1])
        earliest = float(items[0][1])
    else:
        s = pd.Series(shares_series).dropna()
        if len(s) < 2:
            return 0.0
        latest = float(s.iloc[-1])
        earliest = float(s.iloc[0])

    if earliest <= 0:
        return 0.0
    return round(float((latest - earliest) / earliest), 4)


def calc_institution_holding_change(
    current_pct: float | None,
    prev_pct: float | None,
) -> float:
    """机构持有比例变化（current - prev）。"""
    cur = float(current_pct) if current_pct is not None else 0.0
    prev = float(prev_pct) if prev_pct is not None else 0.0
    return round(cur - prev, 4)


def calc_dividend_count_5y(
    dividends: pd.DataFrame | list | None,
    as_of_date=None,
) -> int:
    """近 5 年分红次数。

    Args:
        dividends: 分红记录。DataFrame 需含 ex_date 列；list 视为日期序列。
        as_of_date: 截止日期，用于界定 5 年窗口；None 用今天。
    """
    if dividends is None:
        return 0
    ref = pd.Timestamp(as_of_date) if as_of_date is not None else pd.Timestamp.now()
    cutoff = ref - pd.DateOffset(years=5)

    if isinstance(dividends, pd.DataFrame):
        if dividends.empty or "ex_date" not in dividends:
            return 0
        dates = pd.to_datetime(dividends["ex_date"], errors="coerce").dropna()
    else:
        dates = pd.to_datetime(pd.Series(dividends), errors="coerce").dropna()

    if dates.empty:
        return 0
    return int(((dates >= cutoff) & (dates <= ref)).sum())


def calc_l4_cashflow(
    shares_series: pd.Series | dict | None = None,
    institution_current: float | None = None,
    institution_prev: float | None = None,
    dividends: pd.DataFrame | list | None = None,
    as_of_date=None,
) -> L4Cashflow:
    """计算 L4 现金流指标。

    Args:
        shares_series: 份额时间序列（用于同比变动）。
        institution_current: 当期机构持有比例。
        institution_prev: 上期机构持有比例。
        dividends: 分红记录。
        as_of_date: 截止日期。
    """
    return L4Cashflow(
        share_change_yoy=calc_share_change_yoy(shares_series),
        institution_holding_change=calc_institution_holding_change(
            institution_current, institution_prev
        ),
        dividend_count_5y=calc_dividend_count_5y(dividends, as_of_date),
    )
