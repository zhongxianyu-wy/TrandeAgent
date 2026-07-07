"""pytest fixtures（Feature #4 indicators）。

提供 MockDataProvider，不依赖真实网络。
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from src.data.provider import DataProvider


def _make_nav_df(
    start: date,
    end: date,
    fund_code: str = "000001",
    seed: int = 42,
    drift: float = 0.0008,
    vol: float = 0.011,
) -> pd.DataFrame:
    """生成确定性日频净值（带上涨漂移 + 噪声），用于风险指标测试。"""
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start=start, end=end, freq="B")  # 工作日
    n = len(dates)
    shocks = rng.normal(loc=drift, scale=vol, size=n)
    rets = shocks
    nav = 1.0 * np.exp(np.cumsum(rets))
    # daily_return 以百分比存储（模拟 AkShareProvider 风格）
    daily_return_pct = rets * 100.0
    df = pd.DataFrame(
        {
            "trade_date": dates.date,
            "unit_nav": np.round(nav, 4),
            "accum_nav": np.round(nav * 1.0, 4),
            "daily_return": np.round(daily_return_pct, 4),
            "is_adjusted": True,
        }
    )
    return df


class MockDataProvider(DataProvider):
    """内存版 DataProvider，返回样例净值/持仓/经理数据。"""

    def __init__(self, nav_map: dict[str, pd.DataFrame] | None = None) -> None:
        self._nav_map = nav_map or {}
        self._call_count: dict[str, int] = {"nav": 0, "holdings": 0, "manager": 0}

    # DataProvider 抽象方法实现
    def list_funds(self, categories=None) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "fund_code": "000001",
                    "fund_name": "华夏成长混合",
                    "fund_type": "混合型-偏股",
                    "fund_category": "active_stock",
                    "manager_names": "王泽实",
                    "establish_date": "2001-12-18",
                    "latest_scale": 27.30,
                    "management_fee": 0.015,
                    "custodian_fee": 0.0025,
                    "history_months": 240,
                },
                {
                    "fund_code": "161725",
                    "fund_name": "招商中证白酒指数",
                    "fund_type": "指数型-股票",
                    "fund_category": "index",
                    "manager_names": "侯昊",
                    "establish_date": "2015-05-27",
                    "latest_scale": 480.0,
                    "management_fee": 0.012,
                    "custodian_fee": 0.002,
                    "history_months": 120,
                },
            ]
        )

    def get_nav(self, fund_code: str, start: date, end: date) -> pd.DataFrame:
        self._call_count["nav"] += 1
        if fund_code in self._nav_map:
            df = self._nav_map[fund_code]
        else:
            # 不同基金用不同 seed，保证收益有差异（用于排名百分位测试）
            try:
                seed = int(fund_code) % 100000
            except ValueError:
                seed = 42
            df = _make_nav_df(start, end, fund_code, seed=seed)
        mask = pd.Series(True, index=df.index)
        dts = pd.to_datetime(df["trade_date"]).dt.date
        mask &= dts >= start
        mask &= dts <= end
        return df[mask].reset_index(drop=True)

    def get_manager(self, fund_code: str) -> pd.DataFrame:
        self._call_count["manager"] += 1
        return pd.DataFrame(
            [
                {
                    "manager_name": "王泽实",
                    "fund_code": fund_code,
                    "start_date": "2020-01-01",
                    "end_date": None,
                    "tenure_years": 6.5,
                    "total_assets": 27.30,
                }
            ]
        )

    def get_holdings(self, fund_code: str, report_date=None) -> pd.DataFrame:
        self._call_count["holdings"] += 1
        # 4 个季度的持仓，用于换手率/漂移检测
        rows = []
        quarters = [
            (date(2025, 3, 31), "Q1"),
            (date(2025, 6, 30), "Q2"),
            (date(2025, 9, 30), "Q3"),
            (date(2025, 12, 31), "Q4"),
        ]
        # 每期 5 只股票，行业分布含价值与成长
        stocks = [
            ("600036", "招商银行", "银行"),
            ("601318", "中国平安", "非银金融"),
            ("000858", "五粮液", "食品饮料"),
            ("300750", "宁德时代", "电气设备"),
            ("002475", "立讯精密", "电子"),
        ]
        # 不同季度持仓权重变化（制造换手 + 轻微漂移）
        weights_by_q = {
            "Q1": [5.0, 4.0, 6.0, 5.5, 4.5],
            "Q2": [5.5, 3.5, 6.5, 5.0, 4.0],
            "Q3": [6.0, 3.0, 7.0, 4.5, 3.5],
            "Q4": [5.0, 4.0, 6.0, 5.5, 4.5],
        }
        for rd, qkey in quarters:
            w = weights_by_q[qkey]
            for (code, name, ind), pct in zip(stocks, w):
                rows.append(
                    {
                        "report_date": rd,
                        "stock_code": code,
                        "stock_name": name,
                        "holding_pct": pct,
                        "industry": ind,
                    }
                )
        df = pd.DataFrame(rows)
        if report_date is not None:
            df = df[pd.to_datetime(df["report_date"]).dt.date == report_date]
        return df.reset_index(drop=True)

    def refresh_incremental(self, fund_codes=None) -> dict:
        return {}

    def refresh_full_backfill(self, fund_codes, years: int = 5) -> dict:
        return {}

    def get_freshness_report(self) -> pd.DataFrame:
        return pd.DataFrame()


@pytest.fixture
def end_date() -> date:
    return date(2026, 7, 4)


@pytest.fixture
def start_date(end_date) -> date:
    return end_date - timedelta(days=365 * 5)


@pytest.fixture
def mock_provider(start_date, end_date) -> MockDataProvider:
    return MockDataProvider()


@pytest.fixture
def nav_df(start_date, end_date) -> pd.DataFrame:
    return _make_nav_df(start_date, end_date)


@pytest.fixture
def holdings_df() -> pd.DataFrame:
    """复用 MockDataProvider 的持仓数据。"""
    p = MockDataProvider()
    return p.get_holdings("000001")
