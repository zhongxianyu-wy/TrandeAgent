"""T13/T14: 纸上模拟器测试（含 30 天 qualified 判定）。"""
from __future__ import annotations

import pytest

from src.arena.forward import DefaultForwardSimulator, ForwardSimulator


class TestForwardSimulator:
    def test_is_forward_simulator(self, nav, strategy):
        sim = DefaultForwardSimulator([strategy], nav)
        assert isinstance(sim, ForwardSimulator)

    def test_update_daily_advances(self, nav, strategy):
        sim = DefaultForwardSimulator([strategy], nav, qualified_days=30)
        assert sim.current_day == 0
        ok = sim.update_daily()
        assert ok is True
        assert sim.current_day == 1

    def test_qualified_after_threshold(self, nav, strategy):
        sim = DefaultForwardSimulator([strategy], nav, qualified_days=30)
        for _ in range(29):
            sim.update_daily()
        assert sim.is_qualified(strategy.strategy_id) is False
        sim.update_daily()  # 第 30 天
        assert sim.is_qualified(strategy.strategy_id) is True

    def test_custom_qualified_days(self, nav, strategy):
        sim = DefaultForwardSimulator([strategy], nav, qualified_days=5)
        sim.run(5)
        assert sim.is_qualified(strategy.strategy_id)

    def test_get_forward_result(self, nav, strategy):
        sim = DefaultForwardSimulator([strategy], nav, qualified_days=10)
        sim.run(20)
        fr = sim.get_forward_result(strategy.strategy_id)
        assert fr.forward_days == 20
        assert len(fr.daily_returns) == 20
        assert fr.is_qualified is True

    def test_not_qualified_below_threshold(self, nav, strategy):
        sim = DefaultForwardSimulator([strategy], nav, qualified_days=30)
        sim.run(10)
        fr = sim.get_forward_result(strategy.strategy_id)
        assert fr.is_qualified is False
        assert fr.forward_days == 10

    def test_run_to_end(self, nav, strategy):
        sim = DefaultForwardSimulator([strategy], nav, qualified_days=30)
        sim.run()  # 全部推进
        assert sim.current_day == len(nav)
        assert sim.update_daily() is False  # 已到末尾

    def test_multi_strategy_independent(self, nav, strategies_multi_domain):
        sim = DefaultForwardSimulator(strategies_multi_domain, nav, qualified_days=10)
        sim.run(15)
        for s in strategies_multi_domain:
            assert sim.is_qualified(s.strategy_id)
        results = sim.get_all_forward_results()
        assert len(results) == len(strategies_multi_domain)

    def test_invalid_qualified_days(self, nav, strategy):
        with pytest.raises(ValueError):
            DefaultForwardSimulator([strategy], nav, qualified_days=0)

    def test_forward_return_calculation(self, nav, strategy):
        """纸上累计收益 = ∏(1+r_i) - 1。"""
        sim = DefaultForwardSimulator([strategy], nav, qualified_days=1)
        sim.run(5)
        fr = sim.get_forward_result(strategy.strategy_id)
        import numpy as np
        expected = float(np.prod([1.0 + r for r in fr.daily_returns]) - 1.0)
        assert abs(fr.forward_return - expected) < 1e-12

    def test_first_day_zero_signal_zero_return(self, nav, strategy):
        """首日使用昨日信号=0，收益应为 0。"""
        sim = DefaultForwardSimulator([strategy], nav, qualified_days=1)
        sim.update_daily()
        fr = sim.get_forward_result(strategy.strategy_id)
        assert fr.daily_returns[0] == 0.0
