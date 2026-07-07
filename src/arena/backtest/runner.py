"""回测引擎抽象接口（T09）。

对应 plan §3 接口契约。下游（ArenaPipeline）只依赖抽象，具体向量化/精细
实现通过 :class:`PandasBacktestRunner` 提供双档（快速扫描 vs 精细回测）。

回测语义：给定基金净值序列与策略（生成持仓信号），逐日计算策略净值曲线，
再算年化收益/夏普/最大回撤/胜率/Calmar。纯 numpy/pandas 向量化实现，
不依赖 vectorbt / backtrader（Python 3.13 兼容性问题）。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.arena.models import BacktestResult, Strategy


class BacktestRunner(ABC):
    """回测引擎抽象。"""

    @abstractmethod
    def run_fast_scan(
        self, strategies: list[Strategy], years: int
    ) -> list[BacktestResult]:
        """快速扫描（向量化、不计手续费/滑点），用于大批量初筛。"""
        raise NotImplementedError

    @abstractmethod
    def run_precise(
        self, strategies: list[Strategy], years: int
    ) -> list[BacktestResult]:
        """精细回测（含手续费 + 滑点），用于 Top-N 复核。"""
        raise NotImplementedError
