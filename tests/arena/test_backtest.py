"""T09/T10/T11/T12: 回测引擎测试（含与手算对比的正确性校验）。"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.arena.backtest.pandas_runner import (
    PandasBacktestRunner,
    vectorized_backtest,
)
from src.arena.backtest.runner import BacktestRunner
from src.arena.backtest.top_n import select_top_for_precise, trigger_precise
from src.arena.models import BacktestResult, Strategy


# ---------- T10 向量化回测正确性 ----------

class TestVectorizedCorrectness:
    def test_full_position_equals_buyhold(self, nav):
        """满仓信号应等于买入持有年化。"""
        sig = pd.Series(1.0, index=nav.index)
        m = vectorized_backtest(nav, sig)
        n = len(nav)
        years = n / 252
        total = nav.iloc[-1] / nav.iloc[0] - 1
        expected = (1 + total) ** (1 / years) - 1
        assert abs(m["annual_return"] - expected) < 1e-9
        assert m["max_drawdown"] <= 0
        assert -1e-9 <= m["win_rate"] <= 1.0 + 1e-9

    def test_zero_position_zero_return(self, nav):
        sig = pd.Series(0.0, index=nav.index)
        m = vectorized_backtest(nav, sig)
        assert abs(m["annual_return"]) < 1e-12
        assert abs(m["max_drawdown"]) < 1e-12
        assert m["calmar"] == 0.0

    def test_costs_reduce_return(self, nav):
        from src.arena.strategies import get_strategy_class
        sig = get_strategy_class("proto_ma_cross")().generate(nav, {"fast": 10, "slow": 30})
        no_cost = vectorized_backtest(nav, sig)
        with_cost = vectorized_backtest(nav, sig, commission_bps=15.0, slippage_bps=5.0)
        # 有成本时年化应更低
        assert with_cost["annual_return"] <= no_cost["annual_return"] + 1e-9

    def test_sharpe_positive_for_upward_nav(self):
        # 单调上涨 → 正收益、正夏普
        nav = pd.Series(np.linspace(1.0, 2.0, 252), index=pd.date_range("2023-01-01", periods=252, freq="B"))
        sig = pd.Series(1.0, index=nav.index)
        m = vectorized_backtest(nav, sig)
        assert m["annual_return"] > 0
        assert m["sharpe"] >= 0

    def test_empty_series_returns_zeros(self):
        nav = pd.Series([], dtype=float)
        sig = pd.Series([], dtype=float)
        m = vectorized_backtest(nav, sig)
        assert m["annual_return"] == 0.0
        assert m["max_drawdown"] == 0.0

    def test_signal_alignment_via_reindex(self, nav):
        # 信号索引乱序/缺列也应对齐
        sig = pd.Series(1.0, index=nav.index[::-1])
        m = vectorized_backtest(nav, sig)
        assert m["annual_return"] == pytest.approx(
            vectorized_backtest(nav, pd.Series(1.0, index=nav.index))["annual_return"]
        )


# ---------- T10/T11 PandasBacktestRunner ----------

class TestPandasBacktestRunner:
    def test_is_backtest_runner(self, nav):
        runner = PandasBacktestRunner(nav)
        assert isinstance(runner, BacktestRunner)

    def test_fast_scan_no_cost(self, nav, strategy):
        runner = PandasBacktestRunner(nav)
        results = runner.run_fast_scan([strategy], years=5)
        assert len(results) == 1
        r = results[0]
        assert isinstance(r, BacktestResult)
        assert r.precise is False
        assert r.strategy_id == strategy.strategy_id
        assert r.backtest_years >= 1

    def test_precise_flag_and_cost(self, nav, strategy):
        runner = PandasBacktestRunner(
            nav,
            precise_commission_bps=15.0,
            precise_slippage_bps=5.0,
        )
        fast = runner.run_fast_scan([strategy], years=5)[0]
        precise = runner.run_precise([strategy], years=5)[0]
        assert precise.precise is True
        assert fast.precise is False
        # 精细回测年化 <= 快速（含成本）
        assert precise.annual_return <= fast.annual_return + 1e-9

    def test_years_truncation(self, nav, strategy):
        runner = PandasBacktestRunner(nav)
        full = runner.run_fast_scan([strategy], years=5)[0]
        two = runner.run_fast_scan([strategy], years=2)[0]
        assert two.backtest_years <= full.backtest_years

    def test_unknown_prototype_raises(self, nav):
        runner = PandasBacktestRunner(nav)
        bad = Strategy(strategy_id="x", prototype_id="proto_unknown", domain="趋势")
        with pytest.raises(KeyError):
            runner.run_fast_scan([bad], years=1)


# ---------- T12 Top-N 触发 ----------

class TestTopNTrigger:
    def test_select_top_n_orders_by_annual_return(self):
        results = [
            BacktestResult(strategy_id=f"s{i}", annual_return=ar, sharpe=1.0,
                           max_drawdown=-0.1, win_rate=0.5, calmar=1.0, backtest_years=5)
            for i, ar in enumerate([0.1, 0.5, 0.3, 0.2])
        ]
        top = select_top_for_precise(results, top_n=2)
        assert [t.strategy_id for t in top] == ["s1", "s2"]

    def test_select_top_n_zero_returns_empty(self):
        results = [BacktestResult(strategy_id="s", annual_return=0.1, sharpe=1.0,
                                  max_drawdown=-0.1, win_rate=0.5, calmar=1.0, backtest_years=5)]
        assert select_top_for_precise(results, top_n=0) == []

    def test_trigger_precise_runs_only_winners(self, nav, strategies_multi_domain):
        runner = PandasBacktestRunner(nav)
        fast = runner.run_fast_scan(strategies_multi_domain, years=3)
        precise = trigger_precise(fast, strategies_multi_domain, runner, years=3, top_n=3)
        assert len(precise) == 3
        assert all(r.precise for r in precise)
        # 精细结果应是快速结果中年化最高的 3 个
        top_ids = {r.strategy_id for r in select_top_for_precise(fast, top_n=3)}
        assert {r.strategy_id for r in precise} == top_ids
