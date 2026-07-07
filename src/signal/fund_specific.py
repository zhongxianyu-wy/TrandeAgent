"""基金专属信号（T09）。

- 大涨大跌异动警报：单日 daily_return 触发阈值（默认 -3% 全基金类型统一）。
  DataProvider 的 daily_return 为百分比数值（如 -3.0 表示 -3%）。
"""
from __future__ import annotations

import pandas as pd

from src.signal.technical import _detail
from src.signal.models import SignalRule

# 默认大跌阈值（百分比），全基金类型统一（plan §6 关键决策）
DEFAULT_INTRADAY_ALERT_THRESHOLD: float = -3.0


def eval_intraday_alert(nav_df: pd.DataFrame, rule: SignalRule) -> dict:
    """T09：大涨大跌异动警报。

    取净值 DataFrame 最新交易日的 daily_return（百分比）与 threshold 比较。
    operator below=大跌（减仓信号），above=大涨（减仓/止盈或观察，这里按减仓处理）。

    Args:
        nav_df: DataProvider.get_nav 返回的 DataFrame，需含 trade_date / daily_return。
        rule: 信号规则，threshold 为百分比阈值（如 -3.0）。
    """
    threshold = rule.threshold if rule.threshold != 0.0 else DEFAULT_INTRADAY_ALERT_THRESHOLD

    daily_ret = _latest_daily_return(nav_df)
    triggered = False
    direction: str | None = None
    reason = ""
    if daily_ret is None:
        return _detail(rule, None, False, None, "")

    if rule.operator == "below" and daily_ret <= threshold:
        triggered, direction = True, "减仓"
        reason = f"【依据：单日涨跌={daily_ret:.2f}% <= {threshold}%】大跌异动警报"
    elif rule.operator == "above" and daily_ret >= threshold:
        triggered, direction = True, "减仓"
        reason = f"【依据：单日涨跌={daily_ret:.2f}% >= {threshold}%】大涨异动警报"
    return _detail(rule, round(daily_ret, 2), triggered, direction, reason)


def _latest_daily_return(nav_df: pd.DataFrame) -> float | None:
    """安全取最新交易日的 daily_return（百分比）。"""
    if nav_df is None or nav_df.empty:
        return None
    if "daily_return" not in nav_df.columns:
        return None
    df = nav_df.sort_values("trade_date")
    series = pd.to_numeric(df["daily_return"], errors="coerce")
    series = series.dropna()
    if series.empty:
        return None
    return float(series.iloc[-1])
