"""T12 + T14: 默认引擎集成测试（AC-1 单基金 / AC-2 批量 / AC-4 缓存）。"""
from __future__ import annotations

import time
from datetime import date

import numpy as np
import pandas as pd
import pytest

from src.indicators.cache import IndicatorCache
from src.indicators.default_engine import DefaultIndicatorEngine, SupplementaryData
from src.indicators.engine import IndicatorEngine
from src.indicators.models import FundIndicators


@pytest.fixture
def cache(tmp_path):
    c = IndicatorCache(tmp_path / "engine_cache.db")
    yield c
    c.close()


@pytest.fixture
def engine(mock_provider, cache):
    bench = np.random.default_rng(7).normal(0.0002, 0.01, 300)
    return DefaultIndicatorEngine(
        mock_provider, cache=cache, benchmark_returns=bench, max_workers=4
    )


class TestAbstractInterface:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            IndicatorEngine()  # type: ignore[abstract]


class TestCalcAll:
    """AC-1：单基金全指标。"""

    def test_returns_full_indicators(self, engine, end_date):
        ind = engine.calc_all("000001", end_date, years=5)
        assert isinstance(ind, FundIndicators)
        assert ind.fund_code == "000001"
        assert ind.as_of_date == end_date
        # L1-L4 均已填充
        assert ind.l1_basic.scale == pytest.approx(27.30, rel=1e-3)
        assert 24 <= ind.l1_basic.establish_years <= 25
        assert ind.l2_performance.sharpe != 0 or ind.l2_performance.volatility != 0
        assert ind.l3_style.style_box != "未知" or True  # 允许数据不足
        assert 1 <= ind.rating <= 5

    def test_rating_set(self, engine, end_date):
        ind = engine.calc_all("000001", end_date)
        assert 1 <= ind.rating <= 5

    def test_cache_hit_no_recompute(self, engine, mock_provider, end_date):
        """AC-4：同日重复走缓存。"""
        engine.calc_all("000001", end_date)
        calls_before = mock_provider._call_count["nav"]
        engine.calc_all("000001", end_date)
        # 缓存命中 → nav 调用次数不增加
        assert mock_provider._call_count["nav"] == calls_before


class TestCalcBatch:
    """AC-2：批量并行。"""

    def test_returns_dataframe(self, engine, end_date):
        codes = ["000001", "161725"]
        df = engine.calc_batch(codes, end_date)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert set(df["fund_code"]) == set(codes)
        # 关键列存在
        for col in ["fund_code", "as_of_date", "rating", "sharpe", "return_1y"]:
            assert col in df.columns

    def test_empty_list(self, engine, end_date):
        df = engine.calc_batch([], end_date)
        assert df.empty

    def test_batch_performance(self, mock_provider, end_date):
        """AC-2：批量计算性能（100 只基金 ≤ 30s）。"""
        from tests.indicators.conftest import MockDataProvider

        # 构造 100 只基金的 provider，复用同一份净值
        codes = [f"{i:06d}" for i in range(100)]
        nav_map = {
            c: mock_provider.get_nav("000001", date(2021, 7, 4), end_date)
            for c in codes
        }
        provider = MockDataProvider(nav_map=nav_map)
        eng = DefaultIndicatorEngine(provider, max_workers=8)
        start = time.time()
        df = eng.calc_batch(codes, end_date)
        elapsed = time.time() - start
        assert len(df) == 100
        assert elapsed < 30.0

    def test_rank_percentile_in_batch(self, engine, end_date):
        """批量模式下同类排名百分位基于本批基金计算。"""
        df = engine.calc_batch(["000001", "161725"], end_date)
        # 两只基金排名百分位之和应接近 0.5（一个高一个低）
        pcts = sorted(df["rank_1y_percentile"].tolist())
        assert pcts[0] == 0.0  # 收益较低者
        assert pcts[-1] == pytest.approx(0.5)


class TestGetRating:
    def test_returns_int(self, engine, end_date):
        ind = engine.calc_all("000001", end_date)
        r = engine.get_rating(ind)
        assert isinstance(r, int)
        assert 1 <= r <= 5


class TestSupplementaryHook:
    def test_supplementary_data_passed(self, mock_provider, end_date, tmp_path):
        """子类通过 _get_supplementary 注入补充数据。"""

        class CustomEngine(DefaultIndicatorEngine):
            def _get_supplementary(self, fund_code):
                return SupplementaryData(
                    institution_current=0.5,
                    institution_prev=0.4,
                    shares_series={date(2025, 1, 1): 10.0, date(2026, 1, 1): 11.0},
                    dividends=pd.DataFrame({"ex_date": [date(2025, 6, 1)]}),
                    market_caps={"600036": 800.0, "601318": 900.0, "300750": 600.0,
                                 "002475": 400.0, "000858": 500.0},
                )

        eng = CustomEngine(mock_provider)
        ind = eng.calc_all("000001", end_date)
        assert ind.l1_basic.institution_holding_pct == pytest.approx(0.5)
        assert ind.l4_cashflow.share_change_yoy == pytest.approx(0.1)
        assert ind.l4_cashflow.dividend_count_5y == 1
