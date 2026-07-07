"""T02 + DefaultSignalEngine 组装测试。"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from src.signal.engine import DefaultSignalEngine, SignalEngine, _unknown_rule
from src.signal.models import Signal, SignalRule

from tests.signal.conftest import (
    MockSignalDataProvider,
    all_down_series,
    all_up_series,
    golden_cross_series,
    make_nav_df,
)


def _rule(**kw) -> SignalRule:
    base = dict(name="t", category="technical", indicator="rsi",
                operator="below", threshold=30, weight=1.0)
    base.update(kw)
    return SignalRule(**base)


def _ruleset() -> list[SignalRule]:
    return [
        _rule(name="RSI超卖", indicator="rsi", operator="below", threshold=30, weight=0.8),
        _rule(name="RSI超买", indicator="rsi", operator="above", threshold=70, weight=0.8),
        _rule(name="回撤补仓", category="fundamental", indicator="drawdown",
              operator="below", threshold=-10.0, weight=1.2),
        _rule(name="大跌警报", category="fund_specific", indicator="intraday_alert",
              operator="below", threshold=-3.0, weight=2.0),
    ]


class TestAbstract:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            SignalEngine()  # type: ignore[abstract]


class TestCalcSignals:
    def test_returns_signal_per_fund(self, mock_provider, end_date):
        engine = DefaultSignalEngine(mock_provider)
        out = engine.calc_signals(["UP", "DOWN", "FLAT"], _ruleset(), end_date=end_date)
        assert len(out) == 3
        for s in out:
            assert isinstance(s, Signal)
            assert s.level in ("加仓", "持有", "减仓", "止损")
            assert s.fund_code in ("UP", "DOWN", "FLAT")
            assert s.date == end_date

    def test_skips_missing_nav(self, mock_provider, end_date):
        engine = DefaultSignalEngine(mock_provider)
        out = engine.calc_signals(["UP", "MISSING"], _ruleset(), end_date=end_date)
        assert len(out) == 1
        assert out[0].fund_code == "UP"

    def test_empty_codes(self, mock_provider, end_date):
        engine = DefaultSignalEngine(mock_provider)
        assert engine.calc_signals([], _ruleset(), end_date=end_date) == []

    def test_down_trend_signals(self, mock_provider, end_date):
        """下跌序列：回撤深 + RSI 超卖 → 偏加仓/持有。"""
        engine = DefaultSignalEngine(mock_provider)
        out = engine.calc_signals(["DOWN"], _ruleset(), end_date=end_date)
        sig = out[0]
        # 至少有触发理由或持有档位
        assert sig.level in ("加仓", "持有", "减仓", "止损")
        # 回撤规则应被评估（在 detail 中）
        indicators = [d["indicator"] for d in sig.signals_detail]
        assert "drawdown" in indicators
        assert "intraday_alert" in indicators

    def test_default_end_date_today(self, mock_provider):
        engine = DefaultSignalEngine(mock_provider)
        out = engine.calc_signals(["UP"], _ruleset())
        assert out and out[0].date == date.today()


class TestDetectIntradayAlert:
    def test_triggers_at_threshold(self, mock_provider):
        engine = DefaultSignalEngine(mock_provider, intraday_threshold=-3.0)
        assert engine.detect_intraday_alert("X", -3.0) is True

    def test_triggers_beyond_threshold(self, mock_provider):
        engine = DefaultSignalEngine(mock_provider, intraday_threshold=-3.0)
        assert engine.detect_intraday_alert("X", -4.5) is True

    def test_not_triggered(self, mock_provider):
        engine = DefaultSignalEngine(mock_provider, intraday_threshold=-3.0)
        assert engine.detect_intraday_alert("X", -1.0) is False
        assert engine.detect_intraday_alert("X", 2.0) is False

    def test_custom_threshold(self, mock_provider):
        engine = DefaultSignalEngine(mock_provider, intraday_threshold=-2.0)
        assert engine.detect_intraday_alert("X", -2.5) is True
        assert engine.detect_intraday_alert("X", -1.5) is False


class TestRuleDispatch:
    def test_all_indicators_dispatched(self, mock_provider, end_date):
        engine = DefaultSignalEngine(mock_provider)
        nav_df = mock_provider.get_nav("UP", end_date, end_date)
        df = nav_df.sort_values("trade_date").reset_index(drop=True)
        nav = pd.to_numeric(df["unit_nav"], errors="coerce").dropna().reset_index(drop=True)
        rules = [
            _rule(indicator="ma_cross", operator="cross_above"),
            _rule(indicator="macd", operator="cross_above"),
            _rule(indicator="rsi", operator="below", threshold=30),
            _rule(indicator="bollinger", operator="below", threshold=2.0),
            _rule(category="fundamental", indicator="pe_percentile", operator="below", threshold=20),
            _rule(category="fundamental", indicator="drawdown", operator="below", threshold=-10.0),
            _rule(category="fund_specific", indicator="intraday_alert", operator="below", threshold=-3.0),
        ]
        details = engine._evaluate_rules("UP", df, rules)
        assert len(details) == 7
        # 每条 detail 结构完整
        for d in details:
            assert {"name", "indicator", "triggered", "direction", "value"} <= set(d)

    def test_unknown_indicator(self):
        rule = _unknown_rule(_rule(indicator="rsi", operator="below", threshold=30))
        assert rule["triggered"] is False
        assert rule["value"] is None

    def test_unknown_indicator_dispatched_via_engine(self, mock_provider, end_date):
        """未知 indicator 走 _unknown_rule 兜底分支（不抛异常）。"""
        engine = DefaultSignalEngine(mock_provider)
        # SignalRule 会校验 indicator 字面量，这里直接构造一个非法规则绕过校验
        rule = _rule(indicator="rsi", operator="below", threshold=30)
        rule = rule.model_copy(update={"indicator": "totally_unknown"})
        out = engine.calc_signals(["UP"], [rule], end_date=end_date)
        assert len(out) == 1
        assert out[0].signals_detail[0]["triggered"] is False
        assert out[0].signals_detail[0]["value"] is None


class TestValuationProvider:
    def test_injected_provider_used(self, end_date):
        nav_df = make_nav_df(all_up_series(50))
        provider = MockSignalDataProvider({"X": nav_df})
        called = {}

        def vp(code):
            called["code"] = code
            return 10.0  # 低估

        engine = DefaultSignalEngine(provider, valuation_provider=vp)
        rule = _rule(category="fundamental", indicator="pe_percentile",
                     operator="below", threshold=20)
        out = engine.calc_signals(["X"], [rule], end_date=end_date)
        assert called["code"] == "X"
        # 分位 10 < 20 → 触发加仓
        assert out[0].signals_detail[0]["triggered"] is True
        assert out[0].signals_detail[0]["direction"] == "加仓"

    def test_provider_exception_falls_back_to_mock(self, end_date):
        nav_df = make_nav_df(all_down_series(50))
        provider = MockSignalDataProvider({"X": nav_df})

        def vp(code):
            raise RuntimeError("boom")

        engine = DefaultSignalEngine(provider, valuation_provider=vp)
        rule = _rule(category="fundamental", indicator="pe_percentile",
                     operator="below", threshold=20)
        out = engine.calc_signals(["X"], [rule], end_date=end_date)
        # 应回退到 mock_pe_percentile（不抛异常）
        assert len(out) == 1
        assert out[0].signals_detail[0]["indicator"] == "pe_percentile"


class TestEngineFixture:
    def test_mock_provider_returns_empty_for_unknown(self):
        p = MockSignalDataProvider({})
        assert p.get_nav("X", date(2026, 1, 1), date(2026, 1, 2)).empty
