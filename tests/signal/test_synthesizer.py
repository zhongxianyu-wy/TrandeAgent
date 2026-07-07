"""T10-T11：综合合成 + 去噪测试。"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from src.signal.models import Signal
from src.signal.synthesizer import (
    denoise,
    is_within_window,
    score_to_level,
    synthesize,
)


class TestScoreToLevel:
    @pytest.mark.parametrize("score,level", [
        (1.0, "加仓"),
        (0.51, "加仓"),
        (0.5, "持有"),
        (0.3, "持有"),
        (0.0, "持有"),
        (-0.3, "持有"),
        (-0.5, "持有"),
        (-0.51, "减仓"),
        (-1.0, "减仓"),
        (-1.01, "止损"),
        (-2.0, "止损"),
    ])
    def test_boundaries(self, score, level):
        assert score_to_level(score) == level


def _detail(name, indicator, triggered, direction, weight=1.0, reason=""):
    return {
        "name": name, "category": "technical", "indicator": indicator,
        "value": 0, "triggered": triggered, "direction": direction,
        "weight": weight, "reason": reason,
    }


class TestSynthesize:
    def test_no_triggered_is_hold(self):
        details = [_detail("a", "rsi", False, None, reason="x")]
        s = synthesize(details, {}, fund_code="000001", date=date(2026, 7, 4))
        assert s.level == "持有"
        assert s.score == 0.0
        assert s.reasons == []

    def test_buy_signals_accumulate(self):
        details = [
            _detail("a", "rsi", True, "加仓", 0.8, "理由A"),
            _detail("b", "ma", True, "加仓", 1.0, "理由B"),
        ]
        s = synthesize(details, {"rsi": 0.8, "ma": 1.0},
                       fund_code="000001", date=date(2026, 7, 4))
        assert s.score == pytest.approx(1.8)
        assert s.level == "加仓"
        assert s.reasons == ["理由A", "理由B"]

    def test_sell_signals_accumulate_to_stop_loss(self):
        details = [
            _detail("a", "rsi", True, "减仓", 0.8, "理由A"),
            _detail("b", "intraday", True, "减仓", 2.0, "理由B"),
        ]
        s = synthesize(details, {"rsi": 0.8, "intraday": 2.0},
                       fund_code="000001", date=date(2026, 7, 4))
        assert s.score == pytest.approx(-2.8)
        assert s.level == "止损"

    def test_weights_override_detail_weight(self):
        details = [_detail("a", "rsi", True, "加仓", 0.1, "理由")]
        # weights 优先级高于 detail.weight
        s = synthesize(details, {"rsi": 5.0},
                       fund_code="000001", date=date(2026, 7, 4))
        assert s.score == pytest.approx(5.0)

    def test_weights_none_uses_detail_weight(self):
        details = [_detail("a", "rsi", True, "加仓", 2.0, "理由")]
        s = synthesize(details, None, fund_code="000001", date=date(2026, 7, 4))
        assert s.score == pytest.approx(2.0)

    def test_unknown_direction_ignored(self):
        details = [_detail("a", "x", True, "观察", 1.0, "理由")]
        s = synthesize(details, {}, fund_code="000001", date=date(2026, 7, 4))
        assert s.score == 0.0

    def test_signals_detail_preserved(self):
        details = [_detail("a", "rsi", True, "加仓", 1.0, "理由")]
        s = synthesize(details, {}, fund_code="000001", date=date(2026, 7, 4))
        # 内容一致（pydantic 会重新构造 list，故按内容比较）
        assert len(s.signals_detail) == 1
        assert s.signals_detail[0]["indicator"] == "rsi"
        assert s.signals_detail[0]["reason"] == "理由"


class TestDenoise:
    def _sig(self, code, dt, level, reasons=None, score=0.0):
        return Signal(fund_code=code, date=dt, level=level,
                      reasons=reasons or [], score=score, signals_detail=[])

    def test_empty(self):
        assert denoise([]) == []

    def test_merge_same_group_within_window(self):
        a = self._sig("000001", date(2026, 7, 4), "加仓", ["r1"], 1.0)
        b = self._sig("000001", date(2026, 7, 4), "加仓", ["r2"], 1.2)
        out = denoise([a, b])
        assert len(out) == 1
        assert set(out[0].reasons) == {"r1", "r2"}
        assert out[0].date == date(2026, 7, 4)

    def test_keep_different_levels(self):
        a = self._sig("000001", date(2026, 7, 4), "加仓")
        b = self._sig("000001", date(2026, 7, 4), "减仓")
        out = denoise([a, b])
        assert len(out) == 2

    def test_keep_different_funds(self):
        a = self._sig("000001", date(2026, 7, 4), "加仓")
        b = self._sig("000002", date(2026, 7, 4), "加仓")
        out = denoise([a, b])
        assert len(out) == 2

    def test_separate_beyond_window(self):
        a = self._sig("000001", date(2026, 7, 1), "加仓", ["r1"])
        b = self._sig("000001", date(2026, 7, 10), "加仓", ["r2"])
        out = denoise([a, b])
        assert len(out) == 2

    def test_dedup_identical_reasons(self):
        a = self._sig("000001", date(2026, 7, 4), "加仓", ["r1", "r2"])
        b = self._sig("000001", date(2026, 7, 5), "加仓", ["r2", "r3"])
        out = denoise([a, b])
        assert len(out) == 1
        assert out[0].reasons == ["r1", "r2", "r3"]

    def test_chained_merge_keeps_latest_date(self):
        a = self._sig("000001", date(2026, 7, 1), "加仓", ["r1"])
        b = self._sig("000001", date(2026, 7, 2), "加仓", ["r2"])
        c = self._sig("000001", date(2026, 7, 3), "加仓", ["r3"])
        out = denoise([a, b, c])
        assert len(out) == 1
        assert out[0].date == date(2026, 7, 3)

    def test_does_not_mutate_input(self):
        a = self._sig("000001", date(2026, 7, 4), "加仓", ["r1"])
        b = self._sig("000001", date(2026, 7, 4), "加仓", ["r2"])
        denoise([a, b])
        assert a.reasons == ["r1"]


class TestIsWithinWindow:
    def test_same_day(self):
        assert is_within_window(date(2026, 7, 4), date(2026, 7, 4))

    def test_one_day(self):
        assert is_within_window(date(2026, 7, 4), date(2026, 7, 5))

    def test_far(self):
        assert not is_within_window(date(2026, 7, 4), date(2026, 7, 20))
