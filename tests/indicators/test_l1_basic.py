"""T03: L1 基本面指标单元测试。"""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from src.indicators.l1_basic import calc_establish_years, calc_l1_basic


@pytest.fixture
def fund_info():
    return {
        "fund_code": "000001",
        "fund_name": "华夏成长混合",
        "establish_date": "2001-12-18",
        "latest_scale": 27.30,
        "management_fee": 0.015,
        "custodian_fee": 0.0025,
    }


@pytest.fixture
def managers_df():
    return pd.DataFrame(
        [
            {"manager_name": "王泽实", "tenure_years": 6.5, "total_assets": 27.3},
            {"manager_name": "前任", "tenure_years": 2.0, "total_assets": 10.0},
        ]
    )


class TestCalcEstablishYears:
    def test_normal(self):
        as_of = date(2026, 7, 4)
        years = calc_establish_years("2001-12-18", as_of)
        assert 24 <= years <= 25

    def test_none(self):
        assert calc_establish_years(None, date(2026, 7, 4)) == 0.0

    def test_nan(self):
        assert calc_establish_years(float("nan"), date(2026, 7, 4)) == 0.0

    def test_invalid(self):
        assert calc_establish_years("not-a-date", date(2026, 7, 4)) == 0.0


class TestCalcL1Basic:
    def test_full_fields(self, fund_info, managers_df):
        l1 = calc_l1_basic(
            fund_info,
            managers_df,
            date(2026, 7, 4),
            institution_holding_pct=0.42,
        )
        assert l1.scale == pytest.approx(27.30, rel=1e-3)
        assert 24 <= l1.establish_years <= 25
        # 取任期最长者
        assert l1.manager_tenure_years == pytest.approx(6.5, rel=1e-3)
        assert l1.institution_holding_pct == pytest.approx(0.42, rel=1e-3)
        assert l1.management_fee == pytest.approx(0.015, rel=1e-3)
        assert l1.custodian_fee == pytest.approx(0.0025, rel=1e-3)

    def test_series_input(self, fund_info, managers_df):
        series = pd.Series(fund_info)
        l1 = calc_l1_basic(series, managers_df, date(2026, 7, 4))
        assert l1.scale == pytest.approx(27.30, rel=1e-3)

    def test_empty_managers(self, fund_info):
        l1 = calc_l1_basic(fund_info, pd.DataFrame(), date(2026, 7, 4))
        assert l1.manager_tenure_years == 0.0

    def test_none_managers(self, fund_info):
        l1 = calc_l1_basic(fund_info, None, date(2026, 7, 4))
        assert l1.manager_tenure_years == 0.0

    def test_no_institution_pct_defaults_zero(self, fund_info, managers_df):
        l1 = calc_l1_basic(fund_info, managers_df, date(2026, 7, 4))
        assert l1.institution_holding_pct == 0.0

    def test_institution_clamped(self, fund_info, managers_df):
        l1 = calc_l1_basic(
            fund_info, managers_df, date(2026, 7, 4), institution_holding_pct=1.5
        )
        assert l1.institution_holding_pct == 1.0
        l1b = calc_l1_basic(
            fund_info, managers_df, date(2026, 7, 4), institution_holding_pct=-0.2
        )
        assert l1b.institution_holding_pct == 0.0

    def test_missing_scale(self, managers_df):
        l1 = calc_l1_basic({}, managers_df, date(2026, 7, 4))
        assert l1.scale == 0.0
        assert l1.management_fee == 0.0
