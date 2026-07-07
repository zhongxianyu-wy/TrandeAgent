"""pytest fixtures（Feature #7 signal-engine）。

提供构造性净值序列（确保特定信号触发）与内存版 DataProvider，不依赖真实网络。
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from src.data.provider import DataProvider


def make_nav_df(nav_values, start: date | None = None) -> pd.DataFrame:
    """把净值数组转成 DataProvider.get_nav 风格的 DataFrame。

    daily_return 由净值推导（百分比），首行为 0。
    """
    if start is None:
        start = date(2025, 1, 1)
    n = len(nav_values)
    dates = [start + timedelta(days=i) for i in range(n)]
    nav = np.asarray(nav_values, dtype=float)
    rets = np.zeros(n)
    if n > 1:
        rets[1:] = (nav[1:] / nav[:-1] - 1.0) * 100.0
    return pd.DataFrame({
        "trade_date": dates,
        "unit_nav": np.round(nav, 4),
        "accum_nav": np.round(nav, 4),
        "daily_return": np.round(rets, 4),
        "is_adjusted": True,
    })


# ----------------------------------------------------------------------
# 构造性净值序列（保证特定信号在最后一天触发）
# ----------------------------------------------------------------------

def golden_cross_series() -> np.ndarray:
    """60 个 1.0 后第 61 天跳到 2.0 → 末尾 MA20 上穿 MA60（金叉）。

    数学验证：diff[-1]=MA20[-1]-MA60[-1]≈0.033>0，diff[-2]=0.0。
    """
    arr = np.ones(61)
    arr[-1] = 2.0
    return arr


def death_cross_series() -> np.ndarray:
    """60 个 1.0 后第 61 天跌到 0.5 → 末尾 MA20 下穿 MA60（死叉）。"""
    arr = np.ones(61)
    arr[-1] = 0.5
    return arr


def macd_buy_series() -> np.ndarray:
    """50 个 1.0 后跳到 2.0 → histogram 由 0 转正 → buy。"""
    arr = np.ones(51)
    arr[-1] = 2.0
    return arr


def macd_sell_series() -> np.ndarray:
    """50 个 1.0 后跌到 0.5 → histogram 由 0 转负 → sell。"""
    arr = np.ones(51)
    arr[-1] = 0.5
    return arr


def all_up_series(n: int = 30) -> np.ndarray:
    """每日 +1% 上涨 → RSI=100。"""
    return 1.0 * (1.01 ** np.arange(n))


def all_down_series(n: int = 30) -> np.ndarray:
    """每日 -1% 下跌 → RSI=0。"""
    return 1.0 * (0.99 ** np.arange(n))


def bollinger_above_series() -> np.ndarray:
    """20 个 1.0 后跳到 5.0 → 价格突破上轨。"""
    arr = np.ones(21)
    arr[-1] = 5.0
    return arr


def bollinger_below_series() -> np.ndarray:
    """20 个 10.0 后跌到 1.0 → 价格跌破下轨。"""
    arr = np.full(21, 10.0)
    arr[-1] = 1.0
    return arr


def up_trend_series(n: int = 120) -> np.ndarray:
    """持续温和上涨（含噪声）→ 用于引擎端到端。"""
    rng = np.random.default_rng(1)
    return np.exp(np.cumsum(rng.normal(0.0015, 0.008, n)))


def down_trend_series(n: int = 120) -> np.ndarray:
    """持续温和下跌。"""
    rng = np.random.default_rng(2)
    return np.exp(np.cumsum(rng.normal(-0.0015, 0.008, n)))


def flat_series(n: int = 120) -> np.ndarray:
    """震荡（零漂移）。"""
    rng = np.random.default_rng(3)
    return np.exp(np.cumsum(rng.normal(0.0, 0.006, n)))


# ----------------------------------------------------------------------
# 内存 DataProvider
# ----------------------------------------------------------------------

class MockSignalDataProvider(DataProvider):
    """按 fund_code 返回预设净值的内存 DataProvider。"""

    def __init__(self, nav_map: dict[str, pd.DataFrame] | None = None) -> None:
        self._nav_map = nav_map or {}

    def list_funds(self, categories=None) -> pd.DataFrame:
        return pd.DataFrame()

    def get_nav(self, fund_code: str, start: date, end: date) -> pd.DataFrame:
        return self._nav_map.get(fund_code, pd.DataFrame())

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


@pytest.fixture
def end_date() -> date:
    return date(2026, 7, 4)


@pytest.fixture
def nav_map(end_date) -> dict[str, pd.DataFrame]:
    """上涨/下跌/震荡三条净值序列（覆盖足够长以计算 MA60/MACD）。"""
    # 让序列结束于 end_date
    up = up_trend_series(150)
    down = down_trend_series(150)
    flat = flat_series(150)
    start = end_date - timedelta(days=149)
    return {
        "UP": make_nav_df(up, start),
        "DOWN": make_nav_df(down, start),
        "FLAT": make_nav_df(flat, start),
    }


@pytest.fixture
def mock_provider(nav_map) -> MockSignalDataProvider:
    return MockSignalDataProvider(nav_map)
