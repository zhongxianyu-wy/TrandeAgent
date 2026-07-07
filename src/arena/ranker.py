"""领域排名器（T16）。

按 8 个投资风格领域分组，综合得分 = 收益×0.5 + 夏普×0.3 + 回撤质量×0.2，
各维度在领域内 min-max 归一化（回撤质量 = 1 + max_drawdown ∈ [0,1]，
越大代表回撤越小越好）。每领域取 Top-5。
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

import numpy as np

from src.arena.models import ArenaRanking, BacktestResult, Strategy

DEFAULT_WEIGHTS = {"return": 0.5, "sharpe": 0.3, "drawdown": 0.2}
DEFAULT_TOP_PER_DOMAIN = 5


def _minmax(arr: np.ndarray) -> np.ndarray:
    """min-max 归一化到 [0,1]；常数列归一化为 0.0。"""
    if len(arr) == 0:
        return arr
    lo = float(np.min(arr))
    hi = float(np.max(arr))
    span = hi - lo
    if span < 1e-12:
        return np.zeros_like(arr)
    return (arr - lo) / span


class ArenaRanker:
    """8 领域 Top-5 排名器。"""

    def __init__(
        self,
        *,
        weights: dict[str, float] | None = None,
        top_per_domain: int = DEFAULT_TOP_PER_DOMAIN,
    ) -> None:
        self._weights = weights or dict(DEFAULT_WEIGHTS)
        self._top = top_per_domain

    def compute_scores(
        self, results: list[BacktestResult]
    ) -> dict[str, float]:
        """对一批（同领域）回测结果计算综合得分，返回 strategy_id -> score。"""
        if not results:
            return {}
        ar = np.array([r.annual_return for r in results], dtype=float)
        sh = np.array([r.sharpe for r in results], dtype=float)
        # 回撤质量：max_drawdown <=0，1+dd ∈ [0,1]，越大越好
        dd_quality = np.array([1.0 + r.max_drawdown for r in results], dtype=float)
        nr = _minmax(ar)
        ns = _minmax(sh)
        nd = _minmax(dd_quality)
        w_ret = self._weights.get("return", 0.5)
        w_sh = self._weights.get("sharpe", 0.3)
        w_dd = self._weights.get("drawdown", 0.2)
        scores = w_ret * nr + w_sh * ns + w_dd * nd
        return {r.strategy_id: float(scores[i]) for i, r in enumerate(results)}

    def rank_by_domain(
        self,
        backtest_results: list[BacktestResult],
        strategies: Iterable[Strategy],
    ) -> list[ArenaRanking]:
        """按领域分组排名，每领域取 Top-N。

        Args:
            backtest_results: 回测结果（作为打分依据）。
            strategies: 对应的策略列表（提供 domain 归组）。

        Returns:
            全部 ArenaRanking（每领域前 Top-N），按 domain、rank 排序。
        """
        strat_by_id = {s.strategy_id: s for s in strategies}
        by_domain: dict[str, list[BacktestResult]] = defaultdict(list)
        for r in backtest_results:
            s = strat_by_id.get(r.strategy_id)
            if s is None:
                continue
            by_domain[s.domain].append(r)

        rankings: list[ArenaRanking] = []
        for domain, results in by_domain.items():
            scores = self.compute_scores(results)
            # 按得分降序
            ordered = sorted(results, key=lambda r: scores[r.strategy_id], reverse=True)
            for rank, r in enumerate(ordered, start=1):
                if rank > self._top:
                    break
                rankings.append(
                    ArenaRanking(
                        strategy_id=r.strategy_id,
                        domain=domain,
                        composite_score=scores[r.strategy_id],
                        rank_in_domain=rank,
                    )
                )
        return rankings
