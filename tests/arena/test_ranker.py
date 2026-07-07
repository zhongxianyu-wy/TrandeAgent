"""T16: 领域排名器测试（8 领域 Top-5）。"""
from __future__ import annotations

import pytest

from src.arena.models import BacktestResult, Strategy
from src.arena.ranker import ArenaRanker, DEFAULT_WEIGHTS
from tests.arena.conftest import make_strategy


def _bt(sid: str, annual: float, sharpe: float, dd: float) -> BacktestResult:
    return BacktestResult(
        strategy_id=sid, annual_return=annual, sharpe=sharpe,
        max_drawdown=dd, win_rate=0.5, calmar=1.0, backtest_years=5,
    )


class TestComputeScores:
    def test_default_weights_sum_to_one(self):
        assert abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 1e-9

    def test_best_strategy_highest_score(self):
        results = [
            _bt("best", 0.30, 2.0, -0.05),
            _bt("mid", 0.10, 1.0, -0.15),
            _bt("worst", -0.05, 0.2, -0.30),
        ]
        scores = ArenaRanker().compute_scores(results)
        assert scores["best"] > scores["mid"] > scores["worst"]

    def test_constant_results_zero_score(self):
        results = [_bt("a", 0.1, 1.0, -0.1), _bt("b", 0.1, 1.0, -0.1)]
        scores = ArenaRanker().compute_scores(results)
        # 全相同 → 归一化为 0
        assert scores["a"] == pytest.approx(0.0, abs=1e-9)
        assert scores["b"] == pytest.approx(0.0, abs=1e-9)


class TestRankByDomain:
    def test_groups_by_domain_and_top5(self, strategies_multi_domain, nav):
        from src.arena.backtest.pandas_runner import PandasBacktestRunner
        runner = PandasBacktestRunner(nav)
        results = runner.run_fast_scan(strategies_multi_domain, years=3)
        rankings = ArenaRanker().rank_by_domain(results, strategies_multi_domain)
        # 每领域不超过 Top-5
        from collections import Counter
        per_domain = Counter(r.domain for r in rankings)
        for d, cnt in per_domain.items():
            assert cnt <= 5
        # 排名从 1 开始
        for r in rankings:
            assert r.rank_in_domain >= 1

    def test_rank_ordering_within_domain(self):
        strategies = [
            make_strategy(strategy_id="t1", domain="趋势"),
            make_strategy(strategy_id="t2", domain="趋势"),
            make_strategy(strategy_id="v1", domain="价值"),
        ]
        results = [
            _bt("t1", 0.30, 2.0, -0.05),
            _bt("t2", 0.10, 1.0, -0.15),
            _bt("v1", 0.20, 1.5, -0.10),
        ]
        rankings = ArenaRanker().rank_by_domain(results, strategies)
        trend = sorted([r for r in rankings if r.domain == "趋势"], key=lambda r: r.rank_in_domain)
        assert trend[0].strategy_id == "t1"  # 更高收益排前
        assert trend[0].rank_in_domain == 1
        assert trend[1].rank_in_domain == 2

    def test_custom_top_per_domain(self):
        strategies = [make_strategy(strategy_id=f"s{i}", domain="趋势") for i in range(7)]
        results = [_bt(f"s{i}", 0.20 - i * 0.01, 1.0, -0.1) for i in range(7)]
        rankings = ArenaRanker(top_per_domain=3).rank_by_domain(results, strategies)
        assert len(rankings) == 3  # 只取前 3

    def test_result_without_strategy_skipped(self):
        results = [_bt("orphan", 0.2, 1.0, -0.1)]
        rankings = ArenaRanker().rank_by_domain(results, [])
        assert rankings == []

    def test_eight_domains_representable(self):
        """确认 8 个领域都能正常分组排名。"""
        from src.arena.models import DOMAINS
        strategies = [make_strategy(strategy_id=d, domain=d, prototype_id="proto_dca") for d in DOMAINS]
        results = [_bt(d, 0.1, 1.0, -0.1) for d in DOMAINS]
        rankings = ArenaRanker().rank_by_domain(results, strategies)
        ranked_domains = {r.domain for r in rankings}
        assert ranked_domains == set(DOMAINS)
