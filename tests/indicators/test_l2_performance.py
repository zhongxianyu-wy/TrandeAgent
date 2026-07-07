"""T04 + T05: L2 业绩指标单元测试（纯 numpy 风险指标）。"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from src.indicators.l2_performance import (
    alpha_beta,
    annualized_volatility,
    calc_l2_performance,
    max_drawdown,
    period_return,
    rank_percentile,
    sharpe_ratio,
)


class TestSharpeRatio:
    def test_basic_positive(self):
        rets = np.array([0.01, 0.02, -0.005, 0.015, 0.008])
        s = sharpe_ratio(rets, rf_annual=0.0)
        assert s > 0

    def test_zero_std_returns_zero(self):
        rets = np.array([0.01, 0.01, 0.01])
        assert sharpe_ratio(rets) == 0.0

    def test_insufficient_samples(self):
        assert sharpe_ratio(np.array([0.01])) == 0.0
        assert sharpe_ratio(np.array([])) == 0.0

    def test_with_rf(self):
        rets = np.array([0.001] * 100)
        # 等于无风险时夏普接近 0
        s = sharpe_ratio(rets, rf_annual=0.001 * 252)
        assert abs(s) < 0.5

    def test_nan_filtered(self):
        rets = np.array([0.01, np.nan, 0.02, np.inf, -0.01])
        s = sharpe_ratio(rets)
        assert isinstance(s, float)


class TestMaxDrawdown:
    def test_known_drawdown(self):
        nav = np.array([1.0, 2.0, 1.5, 3.0])
        # 回撤 -25% at index 2
        assert max_drawdown(nav) == pytest.approx(-0.25, rel=1e-6)

    def test_no_drawdown(self):
        nav = np.array([1.0, 2.0, 3.0, 4.0])
        assert max_drawdown(nav) == 0.0

    def test_insufficient(self):
        assert max_drawdown(np.array([1.0])) == 0.0
        assert max_drawdown(np.array([])) == 0.0

    def test_negative_is_nonpositive(self):
        nav = np.array([1.0, 0.5, 0.8, 0.4])
        dd = max_drawdown(nav)
        assert dd <= 0


class TestVolatility:
    def test_known(self):
        rets = np.array([0.01, -0.01, 0.01, -0.01])
        vol = annualized_volatility(rets)
        expected = np.std(rets, ddof=1) * np.sqrt(252)
        assert vol == pytest.approx(expected, rel=1e-6)

    def test_insufficient(self):
        assert annualized_volatility(np.array([0.01])) == 0.0


class TestAlphaBeta:
    def test_beta_one_correlated(self):
        rng = np.random.default_rng(0)
        bench = rng.normal(0.001, 0.01, 500)
        rets = 1.2 * bench + 0.0001  # beta≈1.2
        _, beta = alpha_beta(rets, bench, rf_annual=0.0)
        assert beta == pytest.approx(1.2, abs=0.05)

    def test_alpha_positive(self):
        rng = np.random.default_rng(1)
        bench = rng.normal(0.0, 0.01, 500)
        rets = bench + 0.001  # 正 alpha
        alpha, beta = alpha_beta(rets, bench, rf_annual=0.0)
        assert beta == pytest.approx(1.0, abs=0.05)
        assert alpha > 0

    def test_zero_variance_benchmark(self):
        rets = np.array([0.01, 0.02, 0.03])
        bench = np.array([0.01, 0.01, 0.01])
        alpha, beta = alpha_beta(rets, bench)
        assert alpha == 0.0
        assert beta == 0.0

    def test_insufficient(self):
        a, b = alpha_beta(np.array([0.01]), np.array([0.01]))
        assert a == 0.0 and b == 0.0


class TestPeriodReturn:
    def test_simple(self):
        nav = np.array([1.0, 1.1, 1.2])
        assert period_return(nav, None) == pytest.approx(0.2)

    def test_windowed(self):
        nav = np.array([1.0, 1.5, 2.0])
        # 最近 1 期
        assert period_return(nav, 1) == pytest.approx(2.0 / 1.5 - 1.0)

    def test_insufficient(self):
        assert period_return(np.array([1.0]), None) == 0.0

    def test_zero_start(self):
        assert period_return(np.array([0.0, 1.0]), None) == 0.0


class TestRankPercentile:
    def test_top_rank(self):
        # 该基金收益最高
        assert rank_percentile(0.20, [0.05, 0.10, 0.15, 0.20]) == 0.0

    def test_bottom_rank(self):
        assert rank_percentile(0.01, [0.05, 0.10, 0.15]) == 1.0

    def test_middle(self):
        peers = [0.05, 0.10, 0.15, 0.20]
        # 收益 0.10：比它高的有 2 个（0.15,0.20），4 个总数 → 0.5
        assert rank_percentile(0.10, peers) == pytest.approx(0.5)

    def test_empty_peers(self):
        assert rank_percentile(0.1, []) == 0.5


class TestCalcL2Performance:
    def test_end_to_end(self, nav_df):
        end = date(2026, 7, 4)
        l2 = calc_l2_performance(nav_df, end)
        # 上行漂移 → 正收益
        assert l2.return_1y > 0
        assert l2.sharpe > 0
        assert l2.volatility > 0
        assert l2.max_drawdown <= 0
        assert 0 <= l2.rank_1y_percentile <= 1

    def test_with_benchmark(self, nav_df):
        end = date(2026, 7, 4)
        bench = np.random.default_rng(7).normal(0.0002, 0.01, 200)
        l2 = calc_l2_performance(nav_df, end, benchmark_returns=bench)
        # 有 benchmark 时应计算出 alpha/beta
        assert isinstance(l2.alpha, float)
        assert isinstance(l2.beta, float)

    def test_with_peers(self, nav_df):
        end = date(2026, 7, 4)
        peers = [0.30, 0.25, 0.20, 0.15, 0.10]
        l2 = calc_l2_performance(nav_df, end, peer_returns=peers)
        assert 0 <= l2.rank_1y_percentile <= 1

    def test_empty_nav(self):
        l2 = calc_l2_performance(pd.DataFrame(), date(2026, 7, 4))
        assert l2.return_1y == 0.0
        assert l2.sharpe == 0.0

    def test_derives_returns_when_missing(self):
        # 无 daily_return 列时由净值推导
        dates = pd.date_range("2026-01-01", periods=10, freq="B")
        df = pd.DataFrame(
            {
                "trade_date": dates.date,
                "unit_nav": np.linspace(1.0, 1.1, 10),
                "accum_nav": np.linspace(1.0, 1.1, 10),
            }
        )
        l2 = calc_l2_performance(df, date(2026, 7, 4))
        assert l2.volatility > 0
