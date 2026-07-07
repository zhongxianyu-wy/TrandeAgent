"""IndicatorEngine 抽象接口（T02）。

对应 plan §3 接口契约。下游（screener/analyzer/signal/arena）只依赖本接口，
具体实现由 default_engine.DefaultIndicatorEngine 提供。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

import pandas as pd

from src.indicators.models import FundIndicators


class IndicatorEngine(ABC):
    """指标计算引擎抽象。

    实现方需保证：
    - calc_all 返回完整的 4 层指标 + 评级
    - calc_batch 并行计算多只基金，输出一行一基金的 DataFrame
    - 同日重复计算走缓存（AC-4）
    """

    @abstractmethod
    def calc_all(
        self, fund_code: str, end: date, years: int = 5
    ) -> FundIndicators:
        """计算单只基金全部指标。

        Args:
            fund_code: 基金代码。
            end: 截止日期。
            years: 回溯年数（默认 5 年）。

        Returns:
            FundIndicators，含 L1-L4 与评级。
        """

    @abstractmethod
    def calc_batch(
        self, fund_codes: list[str], end: date, years: int = 5
    ) -> pd.DataFrame:
        """批量并行计算多只基金指标。

        Args:
            fund_codes: 基金代码列表。
            end: 截止日期。
            years: 回溯年数。

        Returns:
            DataFrame，一行一基金，包含 fund_code、as_of_date 及各层关键指标列。
        """

    @abstractmethod
    def get_rating(self, indicators: FundIndicators) -> int:
        """根据已计算指标给出 1-5 星评级（规则加权）。

        Args:
            indicators: 已计算好的 FundIndicators。

        Returns:
            1-5 的整数评级。
        """
