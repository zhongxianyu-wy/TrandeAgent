"""集成测试：观察池端到端 + 去噪 + 大跌即时检测（AC-1/AC-2/AC-3）。

构造上涨/下跌/震荡三种净值序列验证信号生成，并测试去噪与大跌检测集成。
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest

from src.signal import DefaultSignalEngine, denoise
from src.signal.models import SignalRule

from tests.signal.conftest import make_nav_df


def _rule(**kw) -> SignalRule:
    base = dict(name="t", category="technical", indicator="rsi",
                operator="below", threshold=30, weight=1.0)
    base.update(kw)
    return SignalRule(**base)


def _full_ruleset() -> list[SignalRule]:
    """覆盖三类信号的完整规则集（模拟 config/signals.yaml）。"""
    return [
        _rule(name="均线金叉", indicator="ma_cross", operator="cross_above", weight=1.0),
        _rule(name="均线死叉", indicator="ma_cross", operator="cross_below", weight=1.0),
        _rule(name="MACD金叉", indicator="macd", operator="cross_above", weight=1.0),
        _rule(name="MACD死叉", indicator="macd", operator="cross_below", weight=1.0),
        _rule(name="RSI超卖", indicator="rsi", operator="below", threshold=30, weight=0.8),
        _rule(name="RSI超买", indicator="rsi", operator="above", threshold=70, weight=0.8),
        _rule(name="布林下轨", indicator="bollinger", operator="below", threshold=2.0, weight=0.8),
        _rule(name="布林上轨", indicator="bollinger", operator="above", threshold=2.0, weight=0.8),
        _rule(name="PE低估", category="fundamental", indicator="pe_percentile",
              operator="below", threshold=20, weight=1.0),
        _rule(name="PE高估", category="fundamental", indicator="pe_percentile",
              operator="above", threshold=80, weight=1.0),
        _rule(name="回撤补仓", category="fundamental", indicator="drawdown",
              operator="below", threshold=-10.0, weight=1.2),
        _rule(name="大跌警报", category="fund_specific", indicator="intraday_alert",
              operator="below", threshold=-3.0, weight=2.0),
    ]


class TestEndToEnd:
    """AC-1：观察池端到端，每只基金返回四档之一 + 附理由。"""

    def test_three_trends(self, mock_provider, end_date):
        engine = DefaultSignalEngine(mock_provider)
        out = engine.calc_signals(["UP", "DOWN", "FLAT"], _full_ruleset(), end_date=end_date)
        assert len(out) == 3
        codes = {s.fund_code for s in out}
        assert codes == {"UP", "DOWN", "FLAT"}

        for s in out:
            # AC-1.1: 四档之一
            assert s.level in ("加仓", "持有", "减仓", "止损")
            # AC-1.3: 每只基金评估了全部规则
            indicators = {d["indicator"] for d in s.signals_detail}
            assert "rsi" in indicators
            assert "drawdown" in indicators
            assert "intraday_alert" in indicators

    def test_triggered_signal_has_reason(self, mock_provider, end_date):
        """AC-1.2/AC-1.3：触发信号必须附理由且含指标值（【依据：...】）。"""
        engine = DefaultSignalEngine(mock_provider)
        out = engine.calc_signals(["UP", "DOWN", "FLAT"], _full_ruleset(), end_date=end_date)
        any_triggered = False
        for s in out:
            for d in s.signals_detail:
                if d["triggered"]:
                    any_triggered = True
                    assert d["reason"]
                    assert "依据" in d["reason"]
        assert any_triggered, "至少应有一条规则被触发"

    def test_score_consistent_with_reasons(self, mock_provider, end_date):
        engine = DefaultSignalEngine(mock_provider)
        out = engine.calc_signals(["UP", "DOWN", "FLAT"], _full_ruleset(), end_date=end_date)
        for s in out:
            triggered = [d for d in s.signals_detail if d["triggered"]]
            expected = 0.0
            for d in triggered:
                if d["direction"] == "加仓":
                    expected += d["weight"]
                elif d["direction"] == "减仓":
                    expected -= d["weight"]
            assert s.score == pytest.approx(round(expected, 4), abs=1e-4)


class TestIntradayAlertIntegration:
    """AC-2：大跌即时检测，不等盘后批量。"""

    def test_big_drop_detected_immediately(self, mock_provider):
        engine = DefaultSignalEngine(mock_provider, intraday_threshold=-3.0)
        # 模拟盘中 -4%
        assert engine.detect_intraday_alert("UP", -4.0) is True
        assert engine.detect_intraday_alert("UP", -2.0) is False


class TestDenoiseIntegration:
    """AC-3：24h 内同基金同档位不重复推送。"""

    def test_same_day_same_level_merged(self):
        a = _mk_signal("000001", date(2026, 7, 4), "加仓", ["r1"])
        b = _mk_signal("000001", date(2026, 7, 4), "加仓", ["r2"])
        out = denoise([a, b])
        assert len(out) == 1

    def test_different_days_kept(self):
        a = _mk_signal("000001", date(2026, 7, 1), "加仓", ["r1"])
        b = _mk_signal("000001", date(2026, 7, 5), "加仓", ["r2"])
        out = denoise([a, b])
        assert len(out) == 2


def _mk_signal(code, dt, level, reasons):
    from src.signal.models import Signal
    return Signal(fund_code=code, date=dt, level=level, reasons=reasons, score=1.0)


class TestEdgeCases:
    def test_short_nav_series_handled(self, end_date):
        """极短净值序列不应崩溃（各评估器有兜底）。"""
        from tests.signal.conftest import MockSignalDataProvider
        nav_df = make_nav_df([1.0, 1.01, 1.02])
        provider = MockSignalDataProvider({"SHORT": nav_df})
        engine = DefaultSignalEngine(provider)
        out = engine.calc_signals(["SHORT"], _full_ruleset(), end_date=end_date)
        assert len(out) == 1
        assert out[0].level in ("加仓", "持有", "减仓", "止损")

    def test_all_fund_codes_processed(self, mock_provider, end_date):
        """多基金批量处理：每只都返回结果。"""
        engine = DefaultSignalEngine(mock_provider)
        codes = ["UP", "DOWN", "FLAT"]
        out = engine.calc_signals(codes, _full_ruleset(), end_date=end_date)
        assert {s.fund_code for s in out} == set(codes)
