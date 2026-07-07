"""纸上模拟器（T13/T14）。

策略上线后每日盘后用真实行情逐日记录收益；至少跑满 ``qualified_days``（默认
30 个交易日）才视为合格（可进 Top-5）。

实现：预计算每条策略在全量净值上的持仓信号序列（O(n)），随后每日按
"昨日信号 × 今日收益"累加，避免重复计算。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

import pandas as pd

from src.arena.models import ForwardResult, Strategy
from src.arena.strategies import get_strategy_class


class ForwardSimulator(ABC):
    """纸上模拟器抽象（plan §3 接口契约）。"""

    @abstractmethod
    def update_daily(self, date: date | None = None) -> bool:
        """推进一个交易日，记录各策略当日收益。返回是否还有后续日期。"""
        raise NotImplementedError

    @abstractmethod
    def is_qualified(self, strategy_id: str) -> bool:
        """策略是否已跑满合格天数。"""
        raise NotImplementedError


class DefaultForwardSimulator(ForwardSimulator):
    """默认纸上模拟器。

    Args:
        strategies: 参与模拟的策略列表。
        nav: 完整净值序列（含历史，按 trade_date 升序）。
        qualified_days: 进 Top-5 所需的最少交易日，默认 30。
        annualization: 年化常数（仅用于语义，目前不影响收益计算）。
    """

    def __init__(
        self,
        strategies: list[Strategy],
        nav: pd.Series,
        *,
        qualified_days: int = 30,
        annualization: int = 252,
    ) -> None:
        if qualified_days <= 0:
            raise ValueError(f"qualified_days 必须 > 0，得到：{qualified_days}")
        self._strategies = {s.strategy_id: s for s in strategies}
        self._nav = nav.astype(float).sort_index()
        self._returns = self._nav.pct_change().fillna(0.0)
        self._annualization = annualization
        self.qualified_days = qualified_days

        # 预计算每条策略的持仓信号序列
        self._signals: dict[str, pd.Series] = {}
        for sid, strat in self._strategies.items():
            proto_cls = get_strategy_class(strat.prototype_id)
            self._signals[sid] = proto_cls().generate(self._nav, strat.params)

        self._daily_returns: dict[str, list[float]] = {sid: [] for sid in self._strategies}
        self._dates: list = []
        self._pos = 0

    def update_daily(self, date: date | None = None) -> bool:
        """推进一个交易日。

        Args:
            date: 可选日期（用于校验/日志）；实际推进严格按 nav 顺序。
        """
        if self._pos >= len(self._nav):
            return False
        i = self._pos
        r = float(self._returns.iloc[i])
        for sid in self._strategies:
            sig_series = self._signals[sid]
            prev_sig = float(sig_series.iloc[i - 1]) if i > 0 else 0.0
            self._daily_returns[sid].append(prev_sig * r)
        self._dates.append(self._nav.index[i])
        self._pos += 1
        return True

    def run(self, days: int | None = None) -> None:
        """连续推进 days 个交易日（None 表示推进到底）。"""
        target = len(self._nav) if days is None else min(self._pos + days, len(self._nav))
        while self._pos < target:
            self.update_daily()

    def is_qualified(self, strategy_id: str) -> bool:
        return len(self._daily_returns.get(strategy_id, [])) >= self.qualified_days

    def get_forward_result(self, strategy_id: str) -> ForwardResult:
        dr = list(self._daily_returns.get(strategy_id, []))
        days = len(dr)
        if days == 0:
            forward_return = 0.0
        else:
            forward_return = float(pd.Series(1.0, index=range(days)).add(dr).prod() - 1.0)
        return ForwardResult(
            strategy_id=strategy_id,
            forward_days=days,
            forward_return=forward_return,
            daily_returns=dr,
            is_qualified=days >= self.qualified_days,
        )

    def get_all_forward_results(self) -> list[ForwardResult]:
        return [self.get_forward_result(sid) for sid in self._strategies]

    @property
    def current_day(self) -> int:
        return self._pos

    @property
    def strategy_ids(self) -> list[str]:
        return list(self._strategies.keys())
