"""T06 + T07 + T08: L3 风格指标单元测试。"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from src.indicators.l3_style import (
    calc_holding_turnover,
    calc_industry_concentration_top3,
    calc_l3_style,
    calc_style_drift,
    classify_style_box,
)


@pytest.fixture
def single_period_holdings():
    return pd.DataFrame(
        [
            {"report_date": date(2025, 12, 31), "stock_code": "600036", "stock_name": "招商银行", "holding_pct": 7.0, "industry": "银行"},
            {"report_date": date(2025, 12, 31), "stock_code": "601318", "stock_name": "中国平安", "holding_pct": 6.0, "industry": "非银金融"},
            {"report_date": date(2025, 12, 31), "stock_code": "300750", "stock_name": "宁德时代", "holding_pct": 5.0, "industry": "电气设备"},
            {"report_date": date(2025, 12, 31), "stock_code": "002475", "stock_name": "立讯精密", "holding_pct": 4.0, "industry": "电子"},
            {"report_date": date(2025, 12, 31), "stock_code": "000858", "stock_name": "五粮液", "holding_pct": 3.0, "industry": "食品饮料"},
        ]
    )


class TestClassifyStyleBox:
    def test_empty(self):
        assert classify_style_box(pd.DataFrame()) == "未知"

    def test_with_market_caps_large_value(self, single_period_holdings):
        caps = {"600036": 800.0, "601318": 900.0, "300750": 600.0, "002475": 400.0, "000858": 500.0}
        label = classify_style_box(single_period_holdings, market_caps=caps)
        # 银行+非银权重高 → 价值；市值大 → 大盘
        assert "大盘" in label
        assert "价值" in label

    def test_growth_dominant(self):
        df = pd.DataFrame(
            [
                {"stock_code": "002475", "holding_pct": 8.0, "industry": "电子"},
                {"stock_code": "300750", "holding_pct": 7.0, "industry": "电气设备"},
                {"stock_code": "000725", "holding_pct": 6.0, "industry": "计算机"},
            ]
        )
        label = classify_style_box(df)
        assert "成长" in label

    def test_no_market_cap_default(self, single_period_holdings):
        label = classify_style_box(single_period_holdings)
        # top1 = 7.0 >= 6.0 → 大盘
        assert "大盘" in label


class TestIndustryConcentration:
    def test_top3(self, single_period_holdings):
        conc = calc_industry_concentration_top3(single_period_holdings)
        # 5 个不同行业各 7,6,5,4,3；top3 = (7+6+5)/25 = 0.72
        assert conc == pytest.approx(0.72, abs=0.01)

    def test_empty(self):
        assert calc_industry_concentration_top3(pd.DataFrame()) == 0.0

    def test_grouped_industries(self):
        df = pd.DataFrame(
            [
                {"holding_pct": 5.0, "industry": "银行"},
                {"holding_pct": 4.0, "industry": "银行"},
                {"holding_pct": 3.0, "industry": "电子"},
                {"holding_pct": 2.0, "industry": "电子"},
                {"holding_pct": 1.0, "industry": "食品"},
            ]
        )
        # 银行=9, 电子=5, 食品=1; top3 = 15/15 = 1.0
        assert calc_industry_concentration_top3(df) == pytest.approx(1.0)


class TestHoldingTurnover:
    def test_multi_period(self, holdings_df):
        t = calc_holding_turnover(holdings_df)
        assert t > 0

    def test_single_period_zero(self, single_period_holdings):
        assert calc_holding_turnover(single_period_holdings) == 0.0

    def test_empty(self):
        assert calc_holding_turnover(pd.DataFrame()) == 0.0


class TestStyleDrift:
    def test_stable_style(self, holdings_df):
        # Mock 数据 4 个季度风格相近 → 漂移较低
        drift = calc_style_drift(holdings_df)
        assert 0.0 <= drift <= 1.0

    def test_empty(self):
        assert calc_style_drift(pd.DataFrame()) == 0.0

    def test_single_period(self, single_period_holdings):
        assert calc_style_drift(single_period_holdings) == 0.0


class TestCalcL3Style:
    def test_full(self, holdings_df):
        l3 = calc_l3_style(holdings_df)
        assert l3.style_box != "未知"
        assert 0 <= l3.industry_concentration_top3 <= 1
        assert l3.holding_turnover >= 0
        assert 0 <= l3.style_drift_score <= 1

    def test_empty(self):
        l3 = calc_l3_style(pd.DataFrame())
        assert l3.style_box == "未知"
