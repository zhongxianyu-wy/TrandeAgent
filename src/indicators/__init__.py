"""指标层（Feature #4）。

提供 4 层指标（L1 基本面 / L2 业绩 / L3 风格 / L4 现金流）计算、评级、缓存与批量并行。
风险指标（夏普/最大回撤/alpha/beta/波动率）纯 numpy 实现，避免 empyrical 兼容问题。
"""
from __future__ import annotations

from src.indicators.cache import IndicatorCache
from src.indicators.default_engine import DefaultIndicatorEngine, SupplementaryData
from src.indicators.engine import IndicatorEngine
from src.indicators.models import (
    FundIndicators,
    L1Basic,
    L2Performance,
    L3Style,
    L4Cashflow,
)
from src.indicators.rating import calc_rating

__all__ = [
    "IndicatorEngine",
    "DefaultIndicatorEngine",
    "SupplementaryData",
    "IndicatorCache",
    "FundIndicators",
    "L1Basic",
    "L2Performance",
    "L3Style",
    "L4Cashflow",
    "calc_rating",
]
