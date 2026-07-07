"""T09 + T10: L4 现金流指标单元测试。"""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from src.indicators.l4_cashflow import (
    calc_dividend_count_5y,
    calc_institution_holding_change,
    calc_l4_cashflow,
    calc_share_change_yoy,
)


class TestShareChange:
    def test_positive_growth(self):
        series = {date(2024, 1, 1): 10.0, date(2025, 1, 1): 12.0}
        assert calc_share_change_yoy(series) == pytest.approx(0.2)

    def test_decline(self):
        series = pd.Series([10.0, 8.0])
        assert calc_share_change_yoy(series) == pytest.approx(-0.2)

    def test_none(self):
        assert calc_share_change_yoy(None) == 0.0

    def test_insufficient(self):
        assert calc_share_change_yoy({date(2024, 1, 1): 10.0}) == 0.0

    def test_zero_base(self):
        series = {date(2024, 1, 1): 0.0, date(2025, 1, 1): 5.0}
        assert calc_share_change_yoy(series) == 0.0


class TestInstitutionChange:
    def test_diff(self):
        assert calc_institution_holding_change(0.50, 0.40) == pytest.approx(0.10)

    def test_none_values(self):
        assert calc_institution_holding_change(None, None) == 0.0


class TestDividendCount:
    def test_within_window(self):
        as_of = date(2026, 7, 4)
        dividends = pd.DataFrame(
            {"ex_date": [date(2022, 6, 1), date(2024, 3, 1), date(2025, 6, 1)]}
        )
        assert calc_dividend_count_5y(dividends, as_of) == 3

    def test_outside_window(self):
        as_of = date(2026, 7, 4)
        dividends = pd.DataFrame(
            {"ex_date": [date(2019, 1, 1), date(2026, 6, 1)]}
        )
        # 2019 超出 5 年窗口
        assert calc_dividend_count_5y(dividends, as_of) == 1

    def test_list_input(self):
        as_of = date(2026, 7, 4)
        assert calc_dividend_count_5y([date(2025, 1, 1)], as_of) == 1

    def test_none(self):
        assert calc_dividend_count_5y(None, date(2026, 7, 4)) == 0

    def test_empty_df(self):
        assert calc_dividend_count_5y(pd.DataFrame(), date(2026, 7, 4)) == 0


class TestCalcL4Cashflow:
    def test_full(self):
        as_of = date(2026, 7, 4)
        l4 = calc_l4_cashflow(
            shares_series={date(2025, 1, 1): 10.0, date(2026, 1, 1): 11.0},
            institution_current=0.50,
            institution_prev=0.45,
            dividends=pd.DataFrame({"ex_date": [date(2025, 6, 1)]}),
            as_of_date=as_of,
        )
        assert l4.share_change_yoy == pytest.approx(0.1)
        assert l4.institution_holding_change == pytest.approx(0.05)
        assert l4.dividend_count_5y == 1

    def test_defaults(self):
        l4 = calc_l4_cashflow()
        assert l4.share_change_yoy == 0.0
        assert l4.institution_holding_change == 0.0
        assert l4.dividend_count_5y == 0
