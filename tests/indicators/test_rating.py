"""T11: 评级算法单元测试。"""
from __future__ import annotations

from datetime import date

import pytest

from src.indicators.models import (
    FundIndicators,
    L1Basic,
    L2Performance,
    L3Style,
    L4Cashflow,
)
from src.indicators.rating import (
    calc_rating,
    score_cashflow,
    score_return,
    score_risk,
    score_stability,
    score_style,
)


def _make_indicators(**overrides) -> FundIndicators:
    base = dict(
        fund_code="000001",
        as_of_date=date(2026, 7, 4),
        l1_basic=L1Basic(scale=50.0, establish_years=10.0, manager_tenure_years=5.0),
        l2_performance=L2Performance(
            return_1y=0.25, sharpe=1.6, rank_1y_percentile=0.1,
            max_drawdown=-0.05, volatility=0.12,
        ),
        l3_style=L3Style(industry_concentration_top3=0.5, style_drift_score=0.0),
        l4_cashflow=L4Cashflow(
            share_change_yoy=0.1, institution_holding_change=0.05, dividend_count_5y=4
        ),
    )
    base.update(overrides)
    return FundIndicators(**base)


class TestDimensionScores:
    def test_stability_high(self):
        assert score_stability(_make_indicators()) >= 4.0

    def test_stability_low(self):
        ind = _make_indicators(
            l1_basic=L1Basic(scale=1.0, establish_years=0.5, manager_tenure_years=0.5)
        )
        assert score_stability(ind) <= 2.0

    def test_return_high(self):
        assert score_return(_make_indicators()) >= 4.0

    def test_return_low(self):
        ind = _make_indicators(
            l2_performance=L2Performance(return_1y=-0.1, sharpe=-0.5, rank_1y_percentile=0.9)
        )
        assert score_return(ind) <= 2.0

    def test_risk_low_drawdown(self):
        assert score_risk(_make_indicators()) >= 4.0

    def test_risk_high(self):
        ind = _make_indicators(
            l2_performance=L2Performance(max_drawdown=-0.5, volatility=0.4)
        )
        assert score_risk(ind) <= 2.0

    def test_style_balanced(self):
        assert score_style(_make_indicators()) >= 4.0

    def test_cashflow_strong(self):
        assert score_cashflow(_make_indicators()) >= 4.0


class TestCalcRating:
    def test_top_fund_five_star(self):
        rating = calc_rating(_make_indicators())
        assert rating == 5

    def test_weak_fund_low_star(self):
        ind = _make_indicators(
            l1_basic=L1Basic(scale=1.0, establish_years=0.5, manager_tenure_years=0.5),
            l2_performance=L2Performance(
                return_1y=-0.2, sharpe=-1.0, rank_1y_percentile=0.95,
                max_drawdown=-0.5, volatility=0.4,
            ),
            l3_style=L3Style(industry_concentration_top3=0.95, style_drift_score=1.0),
            l4_cashflow=L4Cashflow(
                share_change_yoy=-0.3, institution_holding_change=-0.1, dividend_count_5y=0
            ),
        )
        rating = calc_rating(ind)
        assert rating <= 2

    def test_rating_range(self):
        """评级始终在 1-5。"""
        ind = _make_indicators()
        for scale in [0, 1, 10, 100, 1000]:
            ind.l1_basic.scale = scale
            r = calc_rating(ind)
            assert 1 <= r <= 5

    def test_default_indicators(self):
        """全默认值（0）也能给出合理评级。"""
        ind = FundIndicators(fund_code="x", as_of_date=date(2026, 1, 1))
        r = calc_rating(ind)
        assert 1 <= r <= 5
