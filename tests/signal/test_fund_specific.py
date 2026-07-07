"""T09：基金专属信号测试（大涨大跌异动警报）。"""
from __future__ import annotations

import pandas as pd
import pytest

from src.signal.fund_specific import (
    DEFAULT_INTRADAY_ALERT_THRESHOLD,
    _latest_daily_return,
    eval_intraday_alert,
)
from src.signal.models import SignalRule

from tests.signal.conftest import make_nav_df


def _rule(operator="below", threshold=-3.0, weight=2.0) -> SignalRule:
    return SignalRule(name="大跌警报", category="fund_specific",
                      indicator="intraday_alert", operator=operator,
                      threshold=threshold, weight=weight)


class TestLatestDailyReturn:
    def test_normal(self):
        df = make_nav_df([1.0, 0.96])  # 末尾 -4%
        assert _latest_daily_return(df) == pytest.approx(-4.0, abs=0.01)

    def test_empty(self):
        assert _latest_daily_return(pd.DataFrame()) is None

    def test_missing_column(self):
        df = pd.DataFrame({"trade_date": [pd.Timestamp("2025-01-01")]})
        assert _latest_daily_return(df) is None

    def test_all_nan(self):
        df = pd.DataFrame({"trade_date": [pd.Timestamp("2025-01-01")],
                           "daily_return": [pd.NA]})
        assert _latest_daily_return(df) is None


class TestEvalIntradayAlert:
    def test_big_drop_triggers(self):
        df = make_nav_df([1.0, 0.96])  # -4%
        d = eval_intraday_alert(df, _rule())
        assert d["triggered"] is True
        assert d["direction"] == "减仓"
        assert "大跌" in d["reason"]
        assert d["value"] == pytest.approx(-4.0, abs=0.1)

    def test_small_drop_not_triggered(self):
        df = make_nav_df([1.0, 0.99])  # -1%
        d = eval_intraday_alert(df, _rule())
        assert d["triggered"] is False
        assert d["reason"] == ""

    def test_big_rise_triggers_above(self):
        df = make_nav_df([1.0, 1.05])  # +5%
        d = eval_intraday_alert(df, _rule(operator="above", threshold=3.0))
        assert d["triggered"] is True
        assert d["direction"] == "减仓"
        assert "大涨" in d["reason"]

    def test_empty_df(self):
        d = eval_intraday_alert(pd.DataFrame(), _rule())
        assert d["triggered"] is False
        assert d["value"] is None

    def test_threshold_zero_falls_back_to_default(self):
        df = make_nav_df([1.0, 0.96])  # -4%
        rule = _rule(threshold=0.0)
        d = eval_intraday_alert(df, rule)
        # threshold=0 → 回退到 DEFAULT_INTRADAY_ALERT_THRESHOLD=-3.0 → 触发
        assert d["triggered"] is True

    def test_default_threshold_constant(self):
        assert DEFAULT_INTRADAY_ALERT_THRESHOLD == -3.0
