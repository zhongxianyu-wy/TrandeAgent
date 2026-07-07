"""Top-N 精细回测触发逻辑（T12）。

从快速扫描结果中选出综合表现最佳的 Top-N（默认 20）策略，对其触发精细回测
（含手续费/滑点）。排序键：年化收益为主、夏普为辅。
"""
from __future__ import annotations

from src.arena.backtest.pandas_runner import PandasBacktestRunner
from src.arena.models import BacktestResult, Strategy


def select_top_for_precise(
    fast_results: list[BacktestResult], top_n: int = 20
) -> list[BacktestResult]:
    """从快速扫描结果选 Top-N（按年化收益降序，夏普次之）。"""
    if top_n <= 0:
        return []
    ranked = sorted(
        fast_results,
        key=lambda r: (r.annual_return, r.sharpe),
        reverse=True,
    )
    return ranked[:top_n]


def trigger_precise(
    fast_results: list[BacktestResult],
    strategies: list[Strategy],
    runner: PandasBacktestRunner,
    *,
    years: int,
    top_n: int = 20,
) -> list[BacktestResult]:
    """对 Top-N 快速胜出者触发精细回测。

    Returns:
        精细回测结果列表（按 Top-N 顺序）。
    """
    top = select_top_for_precise(fast_results, top_n=top_n)
    strat_by_id = {s.strategy_id: s for s in strategies}
    winners: list[Strategy] = []
    for r in top:
        s = strat_by_id.get(r.strategy_id)
        if s is not None:
            winners.append(s)
    return runner.run_precise(winners, years)
