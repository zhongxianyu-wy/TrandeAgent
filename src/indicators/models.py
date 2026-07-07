"""Pydantic 指标模型（T01）。

对应 plan §2 / spec §3 的 4 层指标结构。字段名统一小写下划线风格。
所有数值字段允许缺失时回退到 0.0，避免上游数据不全导致整层计算失败。
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


QualityTag = Literal["good", "medium", "bad"]


class L1Basic(BaseModel):
    """L1 基本面指标。"""

    scale: float = 0.0  # 最新规模（亿元）
    establish_years: float = 0.0  # 成立年限
    manager_tenure_years: float = 0.0  # 现任经理任期（年）
    institution_holding_pct: float = 0.0  # 机构持有比例 [0,1]
    management_fee: float = 0.0  # 管理费率
    custodian_fee: float = 0.0  # 托管费率


class L2Performance(BaseModel):
    """L2 业绩指标（纯 numpy 实现风险指标）。"""

    return_1y: float = 0.0
    return_3y: float = 0.0
    return_5y: float = 0.0
    rank_1y_percentile: float = 0.0  # 同类排名百分位 [0,1]，越小越靠前
    max_drawdown: float = 0.0  # 最大回撤（负值）
    sharpe: float = 0.0  # 年化夏普比率
    volatility: float = 0.0  # 年化波动率
    alpha: float = 0.0  # 年化 alpha
    beta: float = 0.0  # beta


class L3Style(BaseModel):
    """L3 风格指标。"""

    style_box: str = "未知"  # 九宫格分类：大盘/中盘/小盘 × 价值/平衡/成长
    industry_concentration_top3: float = 0.0  # 前 3 大行业集中度 [0,1]
    holding_turnover: float = 0.0  # 持仓换手率
    style_drift_score: float = 0.0  # 风格漂移得分 [0,1]，越小越稳定


class L4Cashflow(BaseModel):
    """L4 现金流指标。"""

    share_change_yoy: float = 0.0  # 份额同比变动
    institution_holding_change: float = 0.0  # 机构持有比例变化
    dividend_count_5y: int = 0  # 近 5 年分红次数


class FundIndicators(BaseModel):
    """单只基金的全部 4 层指标 + 评级。"""

    fund_code: str
    as_of_date: date
    l1_basic: L1Basic = Field(default_factory=L1Basic)
    l2_performance: L2Performance = Field(default_factory=L2Performance)
    l3_style: L3Style = Field(default_factory=L3Style)
    l4_cashflow: L4Cashflow = Field(default_factory=L4Cashflow)
    rating: int = 0  # 1-5 星，0 表示未评级


def tag_for_scale(scale: float) -> QualityTag:
    """规模好/中/差阈值（research.md §4.1 简化）。"""
    if scale >= 20.0:
        return "good"
    if scale >= 5.0:
        return "medium"
    return "bad"


def tag_for_fee(fee: float) -> QualityTag:
    """管理费率好/中/差（越低越好）。"""
    if fee > 0 and fee <= 0.012:
        return "good"
    if fee <= 0.018:
        return "medium"
    return "bad"


def tag_for_drawdown(dd: float) -> QualityTag:
    """最大回撤好/中/差（负值，越接近 0 越好）。"""
    if dd >= -0.10:
        return "good"
    if dd >= -0.25:
        return "medium"
    return "bad"


def tag_for_sharpe(sharpe: float) -> QualityTag:
    """夏普比率好/中/差。"""
    if sharpe >= 1.0:
        return "good"
    if sharpe >= 0.5:
        return "medium"
    return "bad"
