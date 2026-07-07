"""pytest fixtures（Feature #5 fund-screener）。

提供样例指标 DataFrame（模拟 calc_batch 产物）+ mock DataProvider，
不依赖真实网络。
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from src.data.provider import DataProvider

# 样例基金：8 只，业绩/规模/风格有梯度，F001 为明显优胜者
# 列名与 DefaultIndicatorEngine._indicators_to_row 一致（扁平）
_SAMPLE_ROWS = [
    # code, return_1y, return_3y, return_5y, sharpe, scale, institution, tenure, max_dd, mgmt_fee, style_box
    ("F001", 0.45, 0.90, 1.50, 1.8, 27.0, 0.55, 6.5, -0.15, 0.015, "大盘成长"),
    ("F002", 0.40, 0.80, 1.30, 1.6, 480.0, 0.60, 8.0, -0.18, 0.012, "大盘价值"),
    ("F003", 0.38, 0.70, 1.10, 1.4, 10.0, 0.40, 3.0, -0.20, 0.015, "中盘成长"),
    ("F004", 0.35, 0.60, 0.90, 1.2, 1.0, 0.20, 1.5, -0.22, 0.018, "小盘成长"),
    ("F005", 0.30, 0.50, 0.70, 1.0, 15.0, 0.35, 2.5, -0.24, 0.015, "中盘平衡"),
    ("F006", 0.20, 0.40, 0.50, 0.8, 20.0, 0.30, 2.0, -0.26, 0.015, "中盘价值"),
    ("F007", 0.10, 0.30, 0.30, 0.4, 30.0, 0.25, 1.0, -0.30, 0.020, "大盘平衡"),
    ("F008", -0.05, 0.10, 0.10, -0.1, 40.0, 0.10, 0.5, -0.40, 0.025, "小盘价值"),
]


def make_sample_indicators(as_of: date | None = None) -> pd.DataFrame:
    """构造样例指标 DataFrame（模拟 calc_batch 扁平输出）。"""
    as_of = as_of or date(2026, 7, 4)
    rows = []
    for (
        code,
        r1,
        r3,
        r5,
        sharpe,
        scale,
        inst,
        tenure,
        mdd,
        fee,
        box,
    ) in _SAMPLE_ROWS:
        rows.append(
            {
                "fund_code": code,
                "as_of_date": as_of,
                "rating": 4,
                "scale": scale,
                "establish_years": 10.0,
                "manager_tenure_years": tenure,
                "institution_holding_pct": inst,
                "management_fee": fee,
                "return_1y": r1,
                "return_3y": r3,
                "return_5y": r5,
                "rank_1y_percentile": 0.0,
                "max_drawdown": mdd,
                "sharpe": sharpe,
                "volatility": 0.18,
                "alpha": 0.02,
                "beta": 0.95,
                "style_box": box,
                "industry_concentration_top3": 0.45,
                "holding_turnover": 1.2,
                "style_drift_score": 0.2,
                "share_change_yoy": 0.1,
                "institution_holding_change": 0.05,
                "dividend_count_5y": 3,
            }
        )
    return pd.DataFrame(rows)


class MockDataProvider(DataProvider):
    """内存版 DataProvider，仅提供 list_funds（screener 不直接拉净值）。"""

    def list_funds(self, categories=None) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"fund_code": r[0], "fund_name": f"基金{r[0]}", "fund_category": "active_stock"}
                for r in _SAMPLE_ROWS
            ]
        )

    def get_nav(self, fund_code: str, start: date, end: date) -> pd.DataFrame:
        return pd.DataFrame()

    def get_manager(self, fund_code: str) -> pd.DataFrame:
        return pd.DataFrame()

    def get_holdings(self, fund_code: str, report_date=None) -> pd.DataFrame:
        return pd.DataFrame()

    def refresh_incremental(self, fund_codes=None) -> dict:
        return {}

    def refresh_full_backfill(self, fund_codes, years: int = 5) -> dict:
        return {}

    def get_freshness_report(self) -> pd.DataFrame:
        return pd.DataFrame()


class MockIndicatorEngine:
    """mock IndicatorEngine：直接返回预置指标 DataFrame。"""

    def __init__(self, indicators: pd.DataFrame | None = None) -> None:
        self._indicators = indicators if indicators is not None else make_sample_indicators()
        self.calc_batch_called = 0

    def calc_batch(self, fund_codes: list[str], end: date, years: int = 5) -> pd.DataFrame:
        self.calc_batch_called += 1
        return self._indicators[
            self._indicators["fund_code"].astype(str).isin(fund_codes)
        ].reset_index(drop=True)


@pytest.fixture
def sample_indicators() -> pd.DataFrame:
    return make_sample_indicators()


@pytest.fixture
def mock_provider() -> MockDataProvider:
    return MockDataProvider()


@pytest.fixture
def mock_engine() -> MockIndicatorEngine:
    return MockIndicatorEngine()


@pytest.fixture
def end_date() -> date:
    return date(2026, 7, 4)


@pytest.fixture
def start_date(end_date) -> date:
    return end_date - timedelta(days=365 * 5)
