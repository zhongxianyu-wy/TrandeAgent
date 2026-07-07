"""T01：Signal / SignalRule Pydantic 模型测试。"""
from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from src.signal.models import Signal, SignalRule


class TestSignalRule:
    def test_default_weight(self):
        r = SignalRule(name="r", category="technical", indicator="rsi",
                       operator="below", threshold=30)
        assert r.weight == 1.0
        assert r.threshold == 30

    def test_negative_weight_rejected(self):
        with pytest.raises(ValidationError):
            SignalRule(name="r", category="technical", indicator="rsi",
                       operator="below", threshold=30, weight=-0.5)

    def test_zero_weight_allowed(self):
        r = SignalRule(name="r", category="technical", indicator="rsi",
                       operator="below", threshold=30, weight=0.0)
        assert r.weight == 0.0

    def test_invalid_category_rejected(self):
        with pytest.raises(ValidationError):
            SignalRule(name="r", category="unknown", indicator="rsi",
                       operator="below", threshold=30)

    def test_invalid_indicator_rejected(self):
        with pytest.raises(ValidationError):
            SignalRule(name="r", category="technical", indicator="nope",
                       operator="below", threshold=30)

    def test_invalid_operator_rejected(self):
        with pytest.raises(ValidationError):
            SignalRule(name="r", category="technical", indicator="rsi",
                       operator="~", threshold=30)


class TestSignal:
    def test_defaults(self):
        s = Signal(fund_code="000001", date=date(2026, 7, 4), level="持有")
        assert s.reasons == []
        assert s.signals_detail == []
        assert s.score == 0.0

    def test_invalid_level_rejected(self):
        with pytest.raises(ValidationError):
            Signal(fund_code="000001", date=date(2026, 7, 4), level="买入")

    def test_full_construction(self):
        s = Signal(
            fund_code="000001", date=date(2026, 7, 4), level="加仓",
            reasons=["【依据：RSI=20 < 30】"], score=0.8,
            signals_detail=[{"indicator": "rsi"}],
        )
        assert s.level == "加仓"
        assert len(s.reasons) == 1
