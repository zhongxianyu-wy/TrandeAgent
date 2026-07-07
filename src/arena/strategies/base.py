"""策略原型抽象基类（T08）。

所有 15 个原型继承 ``StrategyBase``，实现 ``generate_signals`` 返回持仓信号序列
（1=满仓持有，0=空仓）。回测引擎据此逐日计算策略净值曲线。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class StrategyBase(ABC):
    """策略原型基类。

    子类需声明 ``prototype_id`` 与 ``default_params``，并实现
    ``generate_signals``。``generate`` 为模板方法：合并默认参数、对齐索引、
    将信号裁剪到 [0,1] 区间并填充缺失值为 0（空仓）。
    """

    prototype_id: str = ""
    default_params: dict = {}

    def generate(self, nav: pd.Series, params: dict | None = None) -> pd.Series:
        """模板方法：生成与 nav 对齐、范围 [0,1] 的持仓信号序列。"""
        merged = {**self.default_params, **(params or {})}
        signals = self.generate_signals(nav, merged)
        signals = signals.reindex(nav.index).fillna(0.0)
        # 裁剪到 [0,1]，避免极端值/做空
        signals = signals.clip(lower=0.0, upper=1.0)
        return signals.astype(float)

    @abstractmethod
    def generate_signals(self, nav: pd.Series, params: dict) -> pd.Series:
        """返回持仓信号序列（1=持有，0=空仓），索引与 nav 对齐。"""
        raise NotImplementedError
