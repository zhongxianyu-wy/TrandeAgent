"""评级算法（T11）。

5 维规则加权，输出 1-5 星。维度：
1. 稳定性（L1 规模 + 成立年限 + 经理任期）
2. 收益（L2 1 年收益 + 夏普 + 排名百分位）
3. 风险（L2 最大回撤 + 波动率，越小越好）
4. 风格（L3 集中度 + 漂移，越分散稳定越好）
5. 现金流（L4 份额变动 + 机构持有变化 + 分红）

各维度评分 1-5，加权求和后四舍五入到 1-5。
"""
from __future__ import annotations

import math

from src.indicators.models import FundIndicators

# 维度权重（归一化）
_WEIGHTS = {
    "stability": 0.20,
    "return": 0.30,
    "risk": 0.25,
    "style": 0.15,
    "cashflow": 0.10,
}


def _clamp_score(x: float) -> int:
    """把分数限制到 [1,5] 整数。"""
    return int(max(1, min(5, round(x))))


def score_stability(indicators: FundIndicators) -> float:
    """稳定性维度（1-5）。"""
    l1 = indicators.l1_basic
    s = 0.0
    # 规模
    if l1.scale >= 50:
        s += 2.0
    elif l1.scale >= 10:
        s += 1.5
    elif l1.scale > 0:
        s += 0.5
    # 成立年限
    if l1.establish_years >= 5:
        s += 1.5
    elif l1.establish_years >= 2:
        s += 1.0
    else:
        s += 0.5
    # 经理任期
    if l1.manager_tenure_years >= 3:
        s += 1.5
    elif l1.manager_tenure_years >= 1:
        s += 1.0
    else:
        s += 0.5
    return s


def score_return(indicators: FundIndicators) -> float:
    """收益维度（1-5）。"""
    l2 = indicators.l2_performance
    s = 0.0
    # 1 年收益
    if l2.return_1y >= 0.20:
        s += 1.5
    elif l2.return_1y >= 0.05:
        s += 1.0
    elif l2.return_1y >= 0:
        s += 0.5
    # 夏普
    if l2.sharpe >= 1.5:
        s += 1.5
    elif l2.sharpe >= 0.8:
        s += 1.0
    elif l2.sharpe > 0:
        s += 0.5
    # 排名百分位（越小越好）
    if l2.rank_1y_percentile <= 0.25:
        s += 2.0
    elif l2.rank_1y_percentile <= 0.50:
        s += 1.0
    else:
        s += 0.5
    return s


def score_risk(indicators: FundIndicators) -> float:
    """风险维度（1-5，回撤/波动越小分越高）。"""
    l2 = indicators.l2_performance
    s = 0.0
    # 最大回撤（负值，越接近 0 越好）
    if l2.max_drawdown >= -0.10:
        s += 2.5
    elif l2.max_drawdown >= -0.25:
        s += 1.5
    else:
        s += 0.5
    # 波动率
    if l2.volatility <= 0.15:
        s += 2.5
    elif l2.volatility <= 0.25:
        s += 1.5
    else:
        s += 0.5
    return s


def score_style(indicators: FundIndicators) -> float:
    """风格维度（1-5，集中度/漂移适中为佳）。"""
    l3 = indicators.l3_style
    s = 0.0
    # 集中度（过低或过高都不佳，0.4-0.7 为佳）
    conc = l3.industry_concentration_top3
    if 0.4 <= conc <= 0.7:
        s += 2.5
    elif 0.3 <= conc <= 0.8:
        s += 1.5
    else:
        s += 0.5
    # 漂移（越小越好）
    if l3.style_drift_score <= 0.33:
        s += 2.5
    elif l3.style_drift_score <= 0.66:
        s += 1.5
    else:
        s += 0.5
    return s


def score_cashflow(indicators: FundIndicators) -> float:
    """现金流维度（1-5，份额增长/机构增持/有分红为佳）。"""
    l4 = indicators.l4_cashflow
    s = 0.0
    # 份额变动（正增长为佳，避免清盘风险）
    if l4.share_change_yoy > 0.05:
        s += 1.5
    elif l4.share_change_yoy >= -0.05:
        s += 1.0
    else:
        s += 0.5
    # 机构持有变化
    if l4.institution_holding_change > 0.02:
        s += 1.0
    elif l4.institution_holding_change >= -0.02:
        s += 0.5
    else:
        s += 0.0
    # 分红
    if l4.dividend_count_5y >= 3:
        s += 2.5
    elif l4.dividend_count_5y >= 1:
        s += 1.5
    else:
        s += 0.5
    return min(s, 5.0)


def calc_rating(indicators: FundIndicators) -> int:
    """综合评级：5 维加权 → 1-5 星。

    Args:
        indicators: 已计算好的 FundIndicators。

    Returns:
        1-5 的整数评级。
    """
    scores = {
        "stability": score_stability(indicators),
        "return": score_return(indicators),
        "risk": score_risk(indicators),
        "style": score_style(indicators),
        "cashflow": score_cashflow(indicators),
    }
    total = 0.0
    for dim, weight in _WEIGHTS.items():
        total += scores[dim] * weight
    if not math.isfinite(total):
        return 0
    return _clamp_score(total)
