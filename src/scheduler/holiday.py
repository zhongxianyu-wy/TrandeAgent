"""交易日判定（plan §3 / T02）。

封装 chinese_calendar 库判定 A 股交易日：
- 周一至周五且非中国法定节假日 → 交易日
- chinese_calendar 每年更新节假日数据，对未来无数据年份
  抛出 NotImplementedError，此时降级为"仅周末过滤"。
"""
from __future__ import annotations

from datetime import date, timedelta

import chinese_calendar as cc
from loguru import logger


def is_trading_day(d: date) -> bool:
    """判定 d 是否为 A 股交易日。

    chinese_calendar 已覆盖中国法定节假日与调休，
    正常年份直接返回 `cc.is_workday(d)`；
    若 d 超出 chinese_calendar 数据范围（抛 NotImplementedError），
    降级为"非周末即交易日"并记录 warning。

    Args:
        d: 待判定日期。

    Returns:
        True 表示交易日。
    """
    try:
        return cc.is_workday(d)
    except NotImplementedError:
        # 该年份 chinese_calendar 暂无节假日数据，降级为周末过滤
        logger.warning(
            "chinese_calendar 无 {} 年节假日数据，降级为周末过滤", d.year
        )
        return d.weekday() < 5  # 0=Mon ... 4=Fri


def trading_days_between(start: date, end: date) -> list[date]:
    """返回 (start, end) 开区间内的交易日列表（升序）。

    不含 start 与 end 本身。start > end 时返回空列表。

    Args:
        start: 起始日期（不含）。
        end: 结束日期（不含）。

    Returns:
        区间内交易日列表（升序）。
    """
    if start >= end:
        return []
    days: list[date] = []
    cur = start + timedelta(days=1)
    while cur < end:
        if is_trading_day(cur):
            days.append(cur)
        cur += timedelta(days=1)
    return days
