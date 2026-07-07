"""基本面信号（T07-T08）。

- T07 PE/PB 历史分位：需指数估值数据，缺数据时回退到基于净值序列的"价格分位"mock。
- T08 回撤深度：复用 #4 的最大回撤思路（纯 numpy 实现，见下），回撤越深越倾向加仓。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.signal.technical import _detail
from src.signal.models import SignalRule


def max_drawdown(nav: pd.Series) -> float:
    """最大回撤（基于净值序列，返回负值或 0，小数形式）。

    与 src.indicators.l2_performance.max_drawdown 同公式，这里独立实现以避免
    强耦合指标层（plan §1：复用思路，不直接依赖）。
    """
    arr = nav.dropna().to_numpy(dtype=float)
    if len(arr) < 2:
        return 0.0
    peak = np.maximum.accumulate(arr)
    drawdown = (arr - peak) / np.where(peak > 0, peak, np.nan)
    drawdown = drawdown[np.isfinite(drawdown)]
    if len(drawdown) == 0:
        return 0.0
    return float(np.min(drawdown))


def mock_pe_percentile(nav: pd.Series) -> float:
    """T07：指数估值数据缺失时的 mock——用最近净值在过去序列中的百分位近似。

    返回 0-100。净值越低 → 分位越低 → 偏低估（加仓）；越高 → 偏高估（减仓）。
    真实场景应注入指数 PE 序列，此处仅作可测试的占位实现。
    """
    arr = nav.dropna().to_numpy(dtype=float)
    if len(arr) < 2:
        return 50.0
    last = arr[-1]
    pct = float(np.mean(arr <= last)) * 100.0
    return round(pct, 2)


def eval_pe_percentile(rule: SignalRule, percentile: float) -> dict:
    """T07：PE/PB 历史分位。operator below=低估加仓，above=高估减仓。

    Args:
        rule: 信号规则，threshold 为分位阈值（0-100）。
        percentile: 当前 PE 历史分位（0-100）。
    """
    triggered = False
    direction: str | None = None
    reason = ""
    if rule.operator == "below" and percentile < rule.threshold:
        triggered, direction = True, "加仓"
        reason = f"【依据：PE分位={percentile:.1f}% < {rule.threshold}%】历史低估，加仓"
    elif rule.operator == "above" and percentile > rule.threshold:
        triggered, direction = True, "减仓"
        reason = f"【依据：PE分位={percentile:.1f}% > {rule.threshold}%】历史高估，减仓"
    return _detail(rule, round(percentile, 2), triggered, direction, reason)


def eval_drawdown(nav: pd.Series, rule: SignalRule) -> dict:
    """T08：回撤深度信号。operator below=回撤深于阈值则加仓（补仓机会）。

    threshold 为回撤百分比阈值（如 -10.0 表示 -10%）。
    """
    mdd = max_drawdown(nav)  # 小数，负值
    mdd_pct = mdd * 100.0
    triggered = False
    direction: str | None = None
    reason = ""
    if rule.operator == "below" and mdd_pct < rule.threshold:
        triggered, direction = True, "加仓"
        reason = (
            f"【依据：最大回撤={mdd_pct:.2f}% < {rule.threshold}%】深度回调，补仓机会"
        )
    elif rule.operator == "above" and mdd_pct > rule.threshold:
        triggered, direction = True, "减仓"
        reason = (
            f"【依据：最大回撤={mdd_pct:.2f}% > {rule.threshold}%】回撤较浅，风险可控"
        )
    return _detail(rule, round(mdd_pct, 2), triggered, direction, reason)
