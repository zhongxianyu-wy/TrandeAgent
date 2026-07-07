"""策略竞技场服务 + 运行态存储（T05/T07 辅助）。

ArenaStore：进程内保存最近一次竞技场运行的产物（策略/排名/回测/净值序列），
以及策略的采用/停用状态。ObservationStore：观察池运行态（配合 ConfigManager
持久化 + 飞书 Base 同步）。
"""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

import pandas as pd

from src.api.schema import (
    BusinessError,
    NotFoundError,
    PaginatedData,
    StrategySummary,
)
from src.api.services.period_service import compute_nav_curve, compute_period_return


class ArenaStore:
    """竞技场运行态存储。"""

    def __init__(self) -> None:
        self.strategies: list[Any] = []  # Strategy 列表
        self.results: list[Any] = []  # BacktestResult 列表
        self.rankings: list[Any] = []  # ArenaRanking 列表
        # strategy_id -> 净值 DataFrame（trade_date/unit_nav），供 timeseries/nav 用
        self.nav_series: dict[str, pd.DataFrame] = {}
        self.adopted: set[str] = set()
        self.disabled: set[str] = set()
        self.last_run: Optional[str] = None

    def load_result(self, run_result: Any) -> None:
        """从 ArenaRunResult 载入。"""
        self.strategies = list(getattr(run_result, "strategies", []) or [])
        self.results = list(getattr(run_result, "precise_results", []) or [])
        if not self.results:
            self.results = list(getattr(run_result, "fast_results", []) or [])
        self.rankings = list(getattr(run_result, "rankings", []) or [])
        self.last_run = date.today().isoformat()

    # ----- 查询辅助 -----
    def _strategy_by_id(self, strategy_id: str) -> Any:
        for s in self.strategies:
            if s.strategy_id == strategy_id:
                return s
        return None

    def _result_by_id(self, strategy_id: str) -> Any:
        for r in self.results:
            if r.strategy_id == strategy_id:
                return r
        return None

    def _ranking_by_id(self, strategy_id: str) -> Any:
        for r in self.rankings:
            if r.strategy_id == strategy_id:
                return r
        return None

    def summary(self, s: Any) -> StrategySummary:
        sid = s.strategy_id
        r = self._result_by_id(sid)
        rank = self._ranking_by_id(sid)
        return StrategySummary(
            strategy_id=sid,
            prototype_id=s.prototype_id,
            domain=s.domain,
            rank_in_domain=getattr(rank, "rank_in_domain", None) if rank else None,
            composite_score=getattr(rank, "composite_score", None) if rank else None,
            annual_return=getattr(r, "annual_return", None) if r else None,
            sharpe=getattr(r, "sharpe", None) if r else None,
            max_drawdown=getattr(r, "max_drawdown", None) if r else None,
            adopted=sid in self.adopted,
            disabled=sid in self.disabled,
        )


class ObservationStore:
    """观察池运行态：内存镜像 + 委托 ConfigManager 持久化。"""

    def __init__(self) -> None:
        self.pool: list[str] = []
        self.initialized: bool = False

    def sync_from_config(self, config_manager: Any) -> None:
        """从 ConfigManager 同步观察池到内存。"""
        if config_manager is None:
            return
        try:
            cfg = config_manager.load()  # type: ignore[attr-defined]
            self.pool = list(getattr(cfg, "observation_pool", []) or [])
            self.initialized = True
        except Exception:  # noqa: BLE001
            self.pool = []
            self.initialized = True


# ---------------------------------------------------------------------------
# 服务函数
# ---------------------------------------------------------------------------
def list_strategies(
    store: ArenaStore,
    *,
    domain: Optional[str] = None,
    sort: str = "score",
    page: int = 1,
    size: int = 20,
) -> PaginatedData:
    """策略列表（按领域过滤 + 排名排序）。"""
    items = [store.summary(s) for s in store.strategies]
    if domain:
        items = [it for it in items if it.domain == domain]
    # 排序
    reverse = True
    if sort == "score":
        items.sort(key=lambda x: (x.composite_score or -1.0), reverse=reverse)
    elif sort == "return":
        items.sort(key=lambda x: (x.annual_return or -1e9), reverse=reverse)
    elif sort == "sharpe":
        items.sort(key=lambda x: (x.sharpe or -1e9), reverse=reverse)
    elif sort == "drawdown":
        # 回撤越小（越接近 0）越靠前
        items.sort(key=lambda x: (x.max_drawdown or -1e9), reverse=True)

    total = len(items)
    start = (page - 1) * size
    page_items = items[start : start + size]
    return PaginatedData(items=page_items, page=page, size=size, total=total)


def get_strategy(store: ArenaStore, strategy_id: str) -> dict:
    """策略详情（含来源/参数/回测结果）。"""
    s = store._strategy_by_id(strategy_id)
    if s is None:
        raise NotFoundError(f"策略 {strategy_id} 不存在")
    r = store._result_by_id(strategy_id)
    rank = store._ranking_by_id(strategy_id)
    data = s.model_dump(mode="json")
    data["backtest"] = r.model_dump(mode="json") if r else None
    data["ranking"] = rank.model_dump(mode="json") if rank else None
    data["adopted"] = strategy_id in store.adopted
    data["disabled"] = strategy_id in store.disabled
    return data


def get_strategy_timeseries(
    store: ArenaStore, strategy_id: str, period: str = "monthly"
):
    """策略周期分析数据。"""
    if store._strategy_by_id(strategy_id) is None:
        raise NotFoundError(f"策略 {strategy_id} 不存在")
    nav_df = store.nav_series.get(strategy_id, pd.DataFrame())
    return compute_period_return(nav_df, period=period)


def get_strategy_nav(
    store: ArenaStore, strategy_id: str, benchmark: Optional[str] = None
):
    """策略净值曲线 + 回撤。"""
    if store._strategy_by_id(strategy_id) is None:
        raise NotFoundError(f"策略 {strategy_id} 不存在")
    nav_df = store.nav_series.get(strategy_id, pd.DataFrame())
    return compute_nav_curve(nav_df)


def get_strategy_cashflow(store: ArenaStore, strategy_id: str) -> dict:
    """策略现金流时序（基于净值序列推导的资金曲线）。"""
    if store._strategy_by_id(strategy_id) is None:
        raise NotFoundError(f"策略 {strategy_id} 不存在")
    nav_df = store.nav_series.get(strategy_id, pd.DataFrame())
    if nav_df.empty:
        return {"dates": [], "flow": []}
    df = nav_df.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df = df.sort_values("trade_date")
    daily_ret = pd.to_numeric(df["unit_nav"], errors="coerce").pct_change().fillna(0.0)
    return {
        "dates": [d.strftime("%Y-%m-%d") for d in df["trade_date"].tolist()],
        "flow": [float(x) for x in daily_ret.tolist()],
    }


def adopt_strategy(store: ArenaStore, strategy_id: str) -> dict:
    """采用策略。"""
    if store._strategy_by_id(strategy_id) is None:
        raise NotFoundError(f"策略 {strategy_id} 不存在")
    if strategy_id in store.disabled:
        raise BusinessError("策略已停用，无法采用")
    store.adopted.add(strategy_id)
    return {"strategy_id": strategy_id, "adopted": True}


def disable_strategy(store: ArenaStore, strategy_id: str) -> dict:
    """停用策略。"""
    if store._strategy_by_id(strategy_id) is None:
        raise NotFoundError(f"策略 {strategy_id} 不存在")
    store.disabled.add(strategy_id)
    store.adopted.discard(strategy_id)
    return {"strategy_id": strategy_id, "disabled": True}


__all__ = [
    "ArenaStore",
    "ObservationStore",
    "list_strategies",
    "get_strategy",
    "get_strategy_timeseries",
    "get_strategy_nav",
    "get_strategy_cashflow",
    "adopt_strategy",
    "disable_strategy",
]
