"""T02: holiday.py 单元测试（plan §5 / spec FR-2）。

使用已知历史日期，避免依赖 chinese_calendar 未来数据更新。
"""
from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from src.scheduler.holiday import is_trading_day, trading_days_between


class TestIsTradingDay:
    """should_run_today 的核心：交易日判定。"""

    @pytest.mark.parametrize(
        "d,expected",
        [
            # 工作日 → True（2026 有数据）
            (date(2026, 7, 6), True),   # 周一
            (date(2026, 7, 7), True),   # 周二
            (date(2026, 6, 26), True),  # 周五
            # 周末 → False
            (date(2026, 7, 4), False),  # 周六
            (date(2026, 7, 5), False),  # 周日
        ],
    )
    def test_workday_and_weekend(self, d: date, expected: bool):
        assert is_trading_day(d) is expected

    @pytest.mark.parametrize(
        "d,expected",
        [
            # 已知节假日（chinese_calendar 覆盖）
            (date(2024, 1, 1), False),   # 元旦（周一）
            (date(2024, 10, 1), False),  # 国庆（周二）
            (date(2024, 10, 7), False),  # 国庆假期（周一）
            (date(2024, 2, 12), False),  # 春节（周一）
            # 节假日后的交易日
            (date(2024, 1, 2), True),    # 元旦后（周二）
            (date(2024, 10, 8), True),   # 国庆后（周二）
        ],
    )
    def test_known_holidays(self, d: date, expected: bool):
        assert is_trading_day(d) is expected

    def test_holiday_not_workday(self):
        """AC-2：节假日判定非交易日。"""
        assert is_trading_day(date(2024, 10, 1)) is False  # 国庆

    def test_fallback_on_no_data(self):
        """未来年份无数据时降级为周末过滤（T02 关键边界）。"""
        # 2027 年 chinese_calendar 暂无数据，会抛 NotImplementedError
        # 周一 → 降级后 True
        assert is_trading_day(date(2027, 6, 7)) is True   # 周一
        # 周六 → 降级后 False
        assert is_trading_day(date(2027, 6, 5)) is False  # 周六

    def test_fallback_only_on_not_implemented(self):
        """其他异常不应被吞掉。"""
        with patch("src.scheduler.holiday.cc.is_workday", side_effect=ValueError("boom")):
            with pytest.raises(ValueError):
                is_trading_day(date(2026, 7, 6))


class TestTradingDaysBetween:
    def test_empty_when_start_ge_end(self):
        assert trading_days_between(date(2026, 7, 7), date(2026, 7, 7)) == []
        assert trading_days_between(date(2026, 7, 8), date(2026, 7, 7)) == []

    def test_exclusive_bounds(self):
        """区间不含端点。"""
        # 07-03(周五,T) ... 07-06(周一,T)：(07-03, 07-06) 开区间无交易日
        result = trading_days_between(date(2026, 7, 3), date(2026, 7, 6))
        assert result == []

    def test_crosses_weekend(self):
        """跨周末：只返回交易日。"""
        # (07-03, 07-07) → [07-06]
        result = trading_days_between(date(2026, 7, 3), date(2026, 7, 7))
        assert result == [date(2026, 7, 6)]

    def test_multiple_days_sorted(self):
        # (06-30, 07-07) → [07-01, 07-02, 07-03, 07-06]
        result = trading_days_between(date(2026, 6, 30), date(2026, 7, 7))
        assert result == [
            date(2026, 7, 1),
            date(2026, 7, 2),
            date(2026, 7, 3),
            date(2026, 7, 6),
        ]

    def test_filters_holiday(self):
        """区间内含节假日应被过滤（2024 国庆周）。"""
        # (2024-09-30, 2024-10-08)：10-01~10-07 假期，返回空
        result = trading_days_between(date(2024, 9, 30), date(2024, 10, 8))
        assert result == []
