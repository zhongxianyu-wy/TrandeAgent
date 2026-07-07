"""L2 业绩指标（T04 + T05）。

纯 numpy/pandas 实现风险指标（夏普/最大回撤/alpha/beta/波动率），
不依赖 empyrical/quantstats（Python 3.13 兼容性问题）。
公式参考 plan §风险指标公式参考，均为标准定义。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.indicators.models import L2Performance

# 年化交易日数（A 股约 244，业界常用 252）
_TRADING_DAYS = 252


# ----------------------------------------------------------------------
# 纯 numpy 风险指标（标准公式）
# ----------------------------------------------------------------------


def sharpe_ratio(
    returns: np.ndarray, rf_annual: float = 0.02, periods: int = _TRADING_DAYS
) -> float:
    """年化夏普比率。

    Args:
        returns: 日收益率序列。
        rf_annual: 年化无风险利率（默认 2%）。
        periods: 年化周期数（默认 252）。

    Returns:
        年化夏普比率；样本不足或 std=0 返回 0.0。
    """
    returns = np.asarray(returns, dtype=float)
    returns = returns[np.isfinite(returns)]
    if len(returns) < 2:
        return 0.0
    excess = returns - rf_annual / periods
    std = np.std(excess, ddof=1)
    if std <= 0:
        return 0.0
    return float(np.mean(excess) / std * np.sqrt(periods))


def max_drawdown(nav: np.ndarray) -> float:
    """最大回撤（基于净值序列，返回负值或 0）。"""
    nav = np.asarray(nav, dtype=float)
    nav = nav[np.isfinite(nav)]
    if len(nav) < 2:
        return 0.0
    peak = np.maximum.accumulate(nav)
    # 避免除零
    drawdown = (nav - peak) / np.where(peak > 0, peak, np.nan)
    drawdown = drawdown[np.isfinite(drawdown)]
    if len(drawdown) == 0:
        return 0.0
    return float(np.min(drawdown))


def annualized_volatility(
    returns: np.ndarray, periods: int = _TRADING_DAYS
) -> float:
    """年化波动率（日收益率标准差 * sqrt(周期数)）。"""
    returns = np.asarray(returns, dtype=float)
    returns = returns[np.isfinite(returns)]
    if len(returns) < 2:
        return 0.0
    std = np.std(returns, ddof=1)
    return float(std * np.sqrt(periods))


def alpha_beta(
    returns: np.ndarray,
    bench: np.ndarray,
    rf_annual: float = 0.02,
    periods: int = _TRADING_DAYS,
) -> tuple[float, float]:
    """计算年化 alpha 与 beta（相对基准）。

    Args:
        returns: 基金日收益率序列。
        bench: 基准日收益率序列（长度需对齐）。
        rf_annual: 年化无风险利率。
        periods: 年化周期数。

    Returns:
        (annualized_alpha, beta)。基准缺失或方差为 0 时返回 (0.0, 0.0)。
    """
    returns = np.asarray(returns, dtype=float)
    bench = np.asarray(bench, dtype=float)
    # 对齐长度
    n = min(len(returns), len(bench))
    if n < 2:
        return 0.0, 0.0
    returns = returns[:n]
    bench = bench[:n]
    mask = np.isfinite(returns) & np.isfinite(bench)
    returns = returns[mask]
    bench = bench[mask]
    if len(returns) < 2:
        return 0.0, 0.0

    rf = rf_annual / periods
    excess_ret = returns - rf
    excess_bench = bench - rf
    var_bench = np.var(excess_bench, ddof=1)
    if var_bench <= 0:
        return 0.0, 0.0
    beta = float(np.cov(excess_ret, excess_bench, ddof=1)[0, 1] / var_bench)
    alpha = float(np.mean(excess_ret) - beta * np.mean(excess_bench))
    return alpha * periods, beta


def period_return(nav: np.ndarray, n_days: int | None) -> float:
    """区间收益率：(end/start - 1)。

    Args:
        nav: 净值序列（升序）。
        n_days: 取最近 n_days 个交易日；None 表示全区间。
    """
    nav = np.asarray(nav, dtype=float)
    nav = nav[np.isfinite(nav)]
    if len(nav) < 2:
        return 0.0
    if n_days is not None and n_days > 0:
        nav = nav[-(n_days + 1):] if len(nav) > n_days else nav
    start = nav[0]
    if start <= 0:
        return 0.0
    return float(nav[-1] / start - 1.0)


# ----------------------------------------------------------------------
# 同类排名百分位（T05）
# ----------------------------------------------------------------------


def rank_percentile(
    fund_return: float, peer_returns: list[float] | np.ndarray | pd.Series
) -> float:
    """同类排名百分位（越小越靠前）。

    百分位 = 比目标收益更高的同类占比。返回 [0, 1]，0 表示该基金收益最高（排名第 1），
    1 表示垫底。

    Args:
        fund_return: 目标基金收益率。
        peer_returns: 同类基金收益率集合（含或不包含目标均可）。

    Returns:
        百分位 [0, 1]。
    """
    peers = np.asarray(list(peer_returns), dtype=float)
    peers = peers[np.isfinite(peers)]
    if len(peers) == 0:
        return 0.5
    # 比目标收益更高的数量占比越多，目标越靠后（百分位越大）
    better = float(np.sum(peers > fund_return))
    total = float(len(peers))
    return round(better / total, 4)


# ----------------------------------------------------------------------
# 组装 L2Performance
# ----------------------------------------------------------------------


def calc_l2_performance(
    nav_df: pd.DataFrame,
    as_of_date,
    benchmark_returns: np.ndarray | pd.Series | None = None,
    peer_returns: list[float] | np.ndarray | pd.Series | None = None,
    rf_annual: float = 0.02,
) -> L2Performance:
    """从净值 DataFrame 计算 L2 业绩指标。

    Args:
        nav_df: get_nav 返回的 DataFrame，需含 unit_nav / daily_return / trade_date。
        as_of_date: 截止日期（未实际使用，保留以匹配签名）。
        benchmark_returns: 基准日收益率（用于 alpha/beta）；None 则不计算。
        peer_returns: 同类基金收益率（用于 rank_1y_percentile）；None 则 0.5。
        rf_annual: 年化无风险利率。

    Returns:
        L2Performance。
    """
    del as_of_date  # 未使用，避免 lint 警告
    if nav_df is None or nav_df.empty:
        return L2Performance()

    df = nav_df.sort_values("trade_date").reset_index(drop=True)

    nav = df["unit_nav"].to_numpy(dtype=float) if "unit_nav" in df else np.array([])
    # 日收益率：优先用 daily_return 列，缺失则由净值推导
    if "daily_return" in df and df["daily_return"].notna().any():
        rets = pd.to_numeric(df["daily_return"], errors="coerce").to_numpy(dtype=float)
    else:
        rets = np.diff(nav, prepend=nav[0]) / np.where(nav > 0, nav, np.nan)
    # daily_return 原始可能是百分比（如 0.5 表示 0.5%），需统一为小数
    # AkShareProvider 输出的 daily_return 是百分比数值（如 0.5），这里归一化
    if len(rets) and np.nanmax(np.abs(rets)) > 1.0:
        rets = rets / 100.0

    return_1y = period_return(nav, _TRADING_DAYS)
    return_3y = period_return(nav, _TRADING_DAYS * 3)
    return_5y = period_return(nav, _TRADING_DAYS * 5)

    sharpe = sharpe_ratio(rets, rf_annual=rf_annual)
    mdd = max_drawdown(nav)
    vol = annualized_volatility(rets)

    if benchmark_returns is not None:
        bench = np.asarray(benchmark_returns, dtype=float)
        alpha, beta = alpha_beta(rets, bench, rf_annual=rf_annual)
    else:
        alpha, beta = 0.0, 0.0

    if peer_returns is not None:
        percentile = rank_percentile(return_1y, peer_returns)
    else:
        percentile = 0.5

    return L2Performance(
        return_1y=round(return_1y, 4),
        return_3y=round(return_3y, 4),
        return_5y=round(return_5y, 4),
        rank_1y_percentile=percentile,
        max_drawdown=round(mdd, 4),
        sharpe=round(sharpe, 4),
        volatility=round(vol, 4),
        alpha=round(alpha, 4),
        beta=round(beta, 4),
    )
