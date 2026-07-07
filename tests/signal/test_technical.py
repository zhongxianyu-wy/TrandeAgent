"""T03-T06：技术面信号测试（MA/MACD/RSI/布林带）。"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.signal.models import SignalRule
from src.signal.technical import (
    bollinger,
    eval_bollinger,
    eval_macd,
    eval_ma_cross,
    eval_rsi,
    ma_cross,
    macd_signal,
    rsi,
)

from tests.signal.conftest import (
    all_down_series,
    all_up_series,
    bollinger_above_series,
    bollinger_below_series,
    death_cross_series,
    golden_cross_series,
    macd_buy_series,
    macd_sell_series,
)


# ----------------------------------------------------------------------
# 原始指标公式
# ----------------------------------------------------------------------

class TestMaCross:
    def test_golden_cross(self):
        nav = pd.Series(golden_cross_series())
        assert ma_cross(nav) == "golden_cross"

    def test_death_cross(self):
        nav = pd.Series(death_cross_series())
        assert ma_cross(nav) == "death_cross"

    def test_flat_no_cross(self):
        nav = pd.Series(np.ones(100))
        assert ma_cross(nav) == "none"

    def test_too_short(self):
        assert ma_cross(pd.Series([1.0, 2.0, 3.0])) == "none"


class TestMacd:
    def test_buy(self):
        nav = pd.Series(macd_buy_series())
        assert macd_signal(nav) == "buy"

    def test_sell(self):
        nav = pd.Series(macd_sell_series())
        assert macd_signal(nav) == "sell"

    def test_flat_none(self):
        nav = pd.Series(np.ones(60))
        assert macd_signal(nav) == "none"

    def test_too_short(self):
        assert macd_signal(pd.Series(np.ones(30))) == "none"


class TestRsi:
    def test_all_up_is_100(self):
        nav = pd.Series(all_up_series(30))
        assert rsi(nav) == pytest.approx(100.0, abs=1e-6)

    def test_all_down_is_0(self):
        nav = pd.Series(all_down_series(30))
        assert rsi(nav) == pytest.approx(0.0, abs=1e-6)

    def test_too_short_returns_50(self):
        assert rsi(pd.Series([1.0, 2.0])) == 50.0


class TestBollinger:
    def test_bands_on_flat(self):
        nav = pd.Series(np.ones(30))
        upper, mid, lower = bollinger(nav)
        assert upper == pytest.approx(1.0)
        assert mid == pytest.approx(1.0)
        assert lower == pytest.approx(1.0)

    def test_too_short_collapses(self):
        upper, mid, lower = bollinger(pd.Series([1.0, 2.0]))
        assert upper == mid == lower == 2.0

    def test_upper_above_mid_above_lower(self):
        rng = np.random.default_rng(0)
        nav = pd.Series(np.exp(np.cumsum(rng.normal(0, 0.01, 50))))
        upper, mid, lower = bollinger(nav)
        assert upper > mid > lower


# ----------------------------------------------------------------------
# 规则评估器
# ----------------------------------------------------------------------

def _rule(**kw) -> SignalRule:
    base = dict(name="t", category="technical", indicator="rsi",
                operator="below", threshold=30, weight=1.0)
    base.update(kw)
    return SignalRule(**base)


class TestEvalMaCross:
    def test_golden_cross_triggers_buy(self):
        rule = _rule(indicator="ma_cross", operator="cross_above")
        d = eval_ma_cross(pd.Series(golden_cross_series()), rule)
        assert d["triggered"] is True
        assert d["direction"] == "加仓"
        assert "MA金叉" in d["reason"]
        assert d["value"] == "golden_cross"

    def test_death_cross_triggers_sell(self):
        rule = _rule(indicator="ma_cross", operator="cross_below")
        d = eval_ma_cross(pd.Series(death_cross_series()), rule)
        assert d["triggered"] is True
        assert d["direction"] == "减仓"

    def test_no_cross_not_triggered(self):
        rule = _rule(indicator="ma_cross", operator="cross_above")
        d = eval_ma_cross(pd.Series(np.ones(100)), rule)
        assert d["triggered"] is False
        assert d["direction"] is None
        assert d["reason"] == ""


class TestEvalMacd:
    def test_buy(self):
        rule = _rule(indicator="macd", operator="cross_above")
        d = eval_macd(pd.Series(macd_buy_series()), rule)
        assert d["triggered"] is True
        assert d["direction"] == "加仓"

    def test_sell(self):
        rule = _rule(indicator="macd", operator="cross_below")
        d = eval_macd(pd.Series(macd_sell_series()), rule)
        assert d["triggered"] is True
        assert d["direction"] == "减仓"

    def test_flat_none(self):
        rule = _rule(indicator="macd", operator="cross_above")
        d = eval_macd(pd.Series(np.ones(60)), rule)
        assert d["triggered"] is False


class TestEvalRsi:
    def test_oversold_triggers_buy(self):
        rule = _rule(indicator="rsi", operator="below", threshold=30)
        d = eval_rsi(pd.Series(all_down_series(30)), rule)
        assert d["triggered"] is True
        assert d["direction"] == "加仓"
        assert "RSI" in d["reason"]

    def test_overbought_triggers_sell(self):
        rule = _rule(indicator="rsi", operator="above", threshold=70)
        d = eval_rsi(pd.Series(all_up_series(30)), rule)
        assert d["triggered"] is True
        assert d["direction"] == "减仓"

    def test_neutral_not_triggered(self):
        rule = _rule(indicator="rsi", operator="below", threshold=30)
        d = eval_rsi(pd.Series(np.ones(40)), rule)
        assert d["triggered"] is False
        assert d["value"] == 50.0


class TestEvalBollinger:
    def test_above_upper_triggers_sell(self):
        rule = _rule(indicator="bollinger", operator="above", threshold=2.0)
        d = eval_bollinger(pd.Series(bollinger_above_series()), rule)
        assert d["triggered"] is True
        assert d["direction"] == "减仓"
        assert isinstance(d["value"], dict)

    def test_below_lower_triggers_buy(self):
        rule = _rule(indicator="bollinger", operator="below", threshold=2.0)
        d = eval_bollinger(pd.Series(bollinger_below_series()), rule)
        assert d["triggered"] is True
        assert d["direction"] == "加仓"

    def test_flat_not_triggered(self):
        rule = _rule(indicator="bollinger", operator="below", threshold=2.0)
        d = eval_bollinger(pd.Series(np.ones(40)), rule)
        assert d["triggered"] is False

    def test_threshold_zero_defaults_to_2(self):
        rule = _rule(indicator="bollinger", operator="above", threshold=0)
        d = eval_bollinger(pd.Series(bollinger_above_series()), rule)
        # threshold=0 应回退到默认 2.0 std 仍触发
        assert d["triggered"] is True
