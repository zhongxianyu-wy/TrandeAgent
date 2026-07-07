"""T01: 指标模型单元测试。"""
from __future__ import annotations

from datetime import date

import pytest

from src.indicators.models import (
    FundIndicators,
    L1Basic,
    L2Performance,
    L3Style,
    L4Cashflow,
    tag_for_drawdown,
    tag_for_fee,
    tag_for_scale,
    tag_for_sharpe,
)


class TestModels:
    def test_l1_basic_defaults(self):
        m = L1Basic()
        assert m.scale == 0.0
        assert m.management_fee == 0.0

    def test_l2_performance_defaults(self):
        m = L2Performance()
        assert m.sharpe == 0.0
        assert m.max_drawdown == 0.0

    def test_l3_style_defaults(self):
        m = L3Style()
        assert m.style_box == "未知"
        assert m.style_drift_score == 0.0

    def test_l4_cashflow_defaults(self):
        m = L4Cashflow()
        assert m.dividend_count_5y == 0

    def test_fund_indicators_assembly(self):
        fi = FundIndicators(
            fund_code="000001",
            as_of_date=date(2026, 7, 4),
            l1_basic=L1Basic(scale=27.3),
            l2_performance=L2Performance(sharpe=1.2),
        )
        assert fi.fund_code == "000001"
        assert fi.l1_basic.scale == 27.3
        assert fi.l2_performance.sharpe == 1.2
        assert fi.l3_style.style_box == "未知"
        assert fi.rating == 0

    def test_fund_indicators_json_roundtrip(self):
        fi = FundIndicators(
            fund_code="000001",
            as_of_date=date(2026, 7, 4),
            l1_basic=L1Basic(scale=10.0),
            rating=4,
        )
        data = fi.model_dump(mode="json")
        fi2 = FundIndicators.model_validate(data)
        assert fi2.fund_code == "000001"
        assert fi2.rating == 4
        assert fi2.l1_basic.scale == 10.0


class TestQualityTags:
    def test_scale_tag(self):
        assert tag_for_scale(50.0) == "good"
        assert tag_for_scale(10.0) == "medium"
        assert tag_for_scale(1.0) == "bad"

    def test_fee_tag(self):
        assert tag_for_fee(0.01) == "good"
        assert tag_for_fee(0.015) == "medium"
        assert tag_for_fee(0.025) == "bad"

    def test_drawdown_tag(self):
        assert tag_for_drawdown(-0.05) == "good"
        assert tag_for_drawdown(-0.20) == "medium"
        assert tag_for_drawdown(-0.40) == "bad"

    def test_sharpe_tag(self):
        assert tag_for_sharpe(1.5) == "good"
        assert tag_for_sharpe(0.7) == "medium"
        assert tag_for_sharpe(0.1) == "bad"
