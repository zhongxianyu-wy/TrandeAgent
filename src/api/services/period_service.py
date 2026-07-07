"""周期分析数据计算（T11）。

基于日频净值序列，用 pandas.resample 聚合为多周期收益率（柱状图数据），
并同步计算基准（沪深 300）的同期收益率。

输入为 DataFrame（含 trade_date / unit_nav 列），输出 :class:`PeriodReturn`。
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from src.api.schema import NavCurve, PeriodReturn

# pandas resample 频率映射
_PERIOD_FREQ = {
    "daily": "B",  # 工作日（日频直接取日收益）
    "weekly": "W-FRI",
    "monthly": "ME",
    "quarterly": "QE",
    "yearly": "YE",
}

# 标签格式
_PERIOD_LABEL_FMT = {
    "daily": "%Y-%m-%d",
    "weekly": "%Y-%m-%d",
    "monthly": "%Y-%m",
    "quarterly": "%Y-Q%q",
    "yearly": "%Y",
}


def _to_nav_series(nav_df: pd.DataFrame) -> pd.Series:
    """从 DataFrame 提取以 trade_date 为索引的单位净值 Series。"""
    if nav_df is None or nav_df.empty:
        return pd.Series(dtype=float)
    df = nav_df.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df = df.sort_values("trade_date").set_index("trade_date")
    if "unit_nav" in df.columns:
        nav = pd.to_numeric(df["unit_nav"], errors="coerce")
    elif "accum_nav" in df.columns:
        nav = pd.to_numeric(df["accum_nav"], errors="coerce")
    else:
        return pd.Series(dtype=float)
    nav = nav.dropna()
    # 同一日取最后一条
    return nav[~nav.index.duplicated(keep="last")]


def _period_returns(nav: pd.Series, period: str) -> tuple[list[str], list[float]]:
    """对净值序列按周期重采样，计算各周期收益率。

    Args:
        nav: 以 datetime 为索引的净值 Series。
        period: daily|weekly|monthly|quarterly|yearly。

    Returns:
        (labels, returns)。
    """
    if nav.empty or period not in _PERIOD_FREQ:
        return [], []
    if period == "daily":
        # 日频：直接取每日收益率
        daily_ret = nav.pct_change().dropna()
        labels = [d.strftime(_PERIOD_LABEL_FMT[period]) for d in daily_ret.index]
        returns = [float(x) for x in daily_ret.tolist()]
        return labels, returns

    freq = _PERIOD_FREQ[period]
    # 取周期末净值
    end_nav = nav.resample(freq).last().dropna()
    if end_nav.empty or len(end_nav) < 1:
        return [], []
    rets = end_nav.pct_change().dropna()
    fmt = _PERIOD_LABEL_FMT[period]
    labels: list[str] = []
    for d in rets.index:
        if period == "quarterly":
            labels.append(f"{d.year}-Q{(d.month - 1) // 3 + 1}")
        else:
            labels.append(d.strftime(fmt))
    return labels, [float(x) for x in rets.tolist()]


def compute_period_return(
    nav_df: pd.DataFrame,
    period: str = "monthly",
    benchmark_df: Optional[pd.DataFrame] = None,
) -> PeriodReturn:
    """计算周期收益率序列（含基准对比）。

    Args:
        nav_df: 基金日频净值 DataFrame。
        period: daily|weekly|monthly|quarterly|yearly。
        benchmark_df: 基准（沪深 300）日频净值 DataFrame；None 时基准收益为 0 列表。
    """
    if period not in _PERIOD_FREQ:
        period = "monthly"

    nav = _to_nav_series(nav_df)
    labels, returns = _period_returns(nav, period)

    bench_returns: list[float] = []
    if benchmark_df is not None and not benchmark_df.empty:
        bench_nav = _to_nav_series(benchmark_df)
        _, bench_returns = _period_returns(bench_nav, period)

    # 与主序列长度对齐（不足补 0.0）
    if len(bench_returns) < len(returns):
        bench_returns = bench_returns + [0.0] * (len(returns) - len(bench_returns))
    elif len(bench_returns) > len(returns):
        bench_returns = bench_returns[: len(returns)]

    return PeriodReturn(
        period=period, labels=labels, returns=returns, benchmark_returns=bench_returns
    )


def compute_nav_curve(
    nav_df: pd.DataFrame,
    benchmark_df: Optional[pd.DataFrame] = None,
) -> NavCurve:
    """计算净值曲线 + 回撤 + 基准对比。

    Args:
        nav_df: 日频净值 DataFrame。
        benchmark_df: 基准日频净值；None 时基准净值留空。
    """
    nav = _to_nav_series(nav_df)
    if nav.empty:
        return NavCurve()

    dates = [d.date() for d in nav.index]
    nav_list = [float(x) for x in nav.tolist()]
    # 回撤：running max 基准下的回撤（负数）
    running_max = np.maximum.accumulate(nav.to_numpy())
    drawdown = nav.to_numpy() / running_max - 1.0
    drawdown_list = [float(x) for x in drawdown.tolist()]

    benchmark_nav: list[float] = []
    if benchmark_df is not None and not benchmark_df.empty:
        bench = _to_nav_series(benchmark_df)
        # 对齐到主序列日期（缺失补 NaN→0）
        aligned = bench.reindex(nav.index, method="ffill").fillna(0.0)
        benchmark_nav = [float(x) for x in aligned.tolist()]

    return NavCurve(
        dates=dates,
        nav=nav_list,
        drawdown=drawdown_list,
        benchmark_nav=benchmark_nav,
    )


__all__ = ["compute_period_return", "compute_nav_curve"]
