"""T07-T08：基本面信号测试（PE 分位 / 回撤深度）。"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.signal.fundamental import (
    eval_drawdown,
    eval_pe_percentile,
    max_drawdown,
    mock_pe_percentile,
)
from src.signal.models import SignalRule


def _rule(**kw) -> SignalRule:
    base = dict(name="f", category="fundamental", indicator="pe_percentile",
                operator="below", threshold=20, weight=1.0)
    base.update(kw)
    return SignalRule(**base)


class TestMaxDrawdown:
    def test_rise_then_fall(self):
        nav = pd.Series([1.0, 1.5, 1.0])
        # 回撤 (1.0-1.5)/1.5 = -0.333
        assert max_drawdown(nav) == pytest.approx(-1 / 3, abs=1e-6)

    def test_monotonic_up_zero_drawdown(self):
        nav = pd.Series(np.linspace(1.0, 2.0, 50))
        assert max_drawdown(nav) == 0.0

    def test_too_short(self):
        assert max_drawdown(pd.Series([1.0])) == 0.0


class TestMockPePercentile:
    def test_all_up_is_high(self):
        nav = pd.Series(np.linspace(1.0, 2.0, 50))
        # 最后一个值是最大 → 百分位 100
        assert mock_pe_percentile(nav) == 100.0

    def test_all_down_is_low(self):
        nav = pd.Series(np.linspace(2.0, 1.0, 50))
        # 最后一个值是最小 → 百分位接近 0
        assert mock_pe_percentile(nav) < 5.0

    def test_too_short(self):
        assert mock_pe_percentile(pd.Series([1.0])) == 50.0


class TestEvalPePercentile:
    def test_low_triggers_buy(self):
        rule = _rule(operator="below", threshold=20)
        d = eval_pe_percentile(rule, 10.0)
        assert d["triggered"] is True
        assert d["direction"] == "加仓"
        assert "PE分位" in d["reason"]

    def test_high_triggers_sell(self):
        rule = _rule(operator="above", threshold=80)
        d = eval_pe_percentile(rule, 90.0)
        assert d["triggered"] is True
        assert d["direction"] == "减仓"

    def test_mid_not_triggered(self):
        rule = _rule(operator="below", threshold=20)
        d = eval_pe_percentile(rule, 50.0)
        assert d["triggered"] is False
        assert d["reason"] == ""


class TestEvalDrawdown:
    def test_deep_drawdown_triggers_buy(self):
        nav = pd.Series([1.0, 1.5, 1.0])  # mdd ≈ -33.33%
        rule = _rule(indicator="drawdown", operator="below", threshold=-10.0)
        d = eval_drawdown(nav, rule)
        assert d["triggered"] is True
        assert d["direction"] == "加仓"
        assert d["value"] == pytest.approx(-33.33, abs=0.1)
        assert "回撤" in d["reason"]

    def test_shallow_drawdown_triggers_sell(self):
        nav = pd.Series(np.linspace(1.0, 2.0, 50))  # mdd = 0%
        rule = _rule(indicator="drawdown", operator="above", threshold=-5.0)
        d = eval_drawdown(nav, rule)
        assert d["triggered"] is True
        assert d["direction"] == "减仓"

    def test_not_triggered(self):
        nav = pd.Series([1.0, 1.05, 1.02])  # mdd ≈ -2.86%
        rule = _rule(indicator="drawdown", operator="below", threshold=-10.0)
        d = eval_drawdown(nav, rule)
        assert d["triggered"] is False
