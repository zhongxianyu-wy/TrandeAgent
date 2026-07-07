"""T01: Pydantic 模型测试。"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.arena.models import (
    DOMAINS,
    ArenaRanking,
    ArenaRunResult,
    BacktestResult,
    CrossCheck,
    Domain,  # noqa: F401  (类型导出校验)
    ForwardResult,
    Strategy,
)


class TestStrategy:
    def test_valid_strategy(self):
        s = Strategy(
            strategy_id="s1",
            prototype_id="proto_4433",
            domain="趋势",
            params={"a": 1},
        )
        assert s.strategy_id == "s1"
        assert s.created_at <= datetime.now(timezone.utc)
        assert s.mind_model_id is None

    def test_prototype_id_must_start_with_proto(self):
        with pytest.raises(ValidationError):
            Strategy(strategy_id="s1", prototype_id="4433", domain="趋势")

    def test_prototype_id_empty_rejected(self):
        with pytest.raises(ValidationError):
            Strategy(strategy_id="s1", prototype_id="", domain="趋势")

    def test_domain_literal_accepts_all_eight(self):
        for d in DOMAINS:
            s = Strategy(strategy_id="s", prototype_id="proto_dca", domain=d)  # type: ignore[arg-type]
            assert s.domain == d

    def test_domain_invalid_rejected(self):
        with pytest.raises(ValidationError):
            Strategy(strategy_id="s", prototype_id="proto_dca", domain="不存在")  # type: ignore[arg-type]

    def test_optional_dims_default_none(self):
        s = Strategy(strategy_id="s", prototype_id="proto_dca", domain="低波")
        assert s.timing_logic is None
        assert s.risk_threshold is None


class TestBacktestResult:
    def test_defaults(self):
        r = BacktestResult(
            strategy_id="s",
            annual_return=0.1,
            sharpe=1.0,
            max_drawdown=-0.2,
            win_rate=0.5,
            calmar=0.5,
            backtest_years=5,
        )
        assert r.precise is False

    def test_negative_drawdown_allowed(self):
        r = BacktestResult(
            strategy_id="s", annual_return=0.0, sharpe=0.0,
            max_drawdown=-0.5, win_rate=0.0, calmar=0.0, backtest_years=1,
        )
        assert r.max_drawdown == -0.5


class TestForwardResult:
    def test_qualified_flag(self):
        f = ForwardResult(strategy_id="s", forward_days=30, forward_return=0.01)
        assert f.is_qualified is False  # 显式构造，由构造方决定

    def test_daily_returns_default_empty(self):
        f = ForwardResult(strategy_id="s", forward_days=0, forward_return=0.0)
        assert f.daily_returns == []


class TestArenaRankingAndCrossCheck:
    def test_ranking(self):
        r = ArenaRanking(strategy_id="s", domain="趋势", composite_score=0.88, rank_in_domain=1)
        assert r.rank_in_domain == 1

    def test_cross_check(self):
        c = CrossCheck(
            strategy_id="s",
            backtest_monthly_return=0.01,
            forward_return=0.05,
            relative_diff=4.0,
            suspicious=True,
        )
        assert c.suspicious is True


class TestArenaRunResult:
    def test_aggregate(self):
        agg = ArenaRunResult(strategies=[], fast_results=[], precise_results=[], rankings=[])
        assert agg.strategies == []
