"""纯 pandas 向量化回测引擎（T10）+ 精细回测（T11）。

实现要点（plan §T10）：
- 昨日信号 × 今日收益 → 策略日收益（信号前移一日，避免未来函数）
- 信号变化（换手）扣手续费 + 滑点
- 累乘得净值曲线，算年化收益/夏普/最大回撤/胜率/Calmar

回测本质是按策略信号逐日计算持仓净值曲线，pandas 向量化可高效完成。
"""
from __future__ import annotations

from loguru import logger

import pandas as pd

from src.arena.backtest.runner import BacktestRunner
from src.arena.models import BacktestResult, Strategy
from src.arena.strategies import get_strategy_class


def vectorized_backtest(
    nav: pd.Series,
    signals: pd.Series,
    *,
    commission_bps: float = 0.0,
    slippage_bps: float = 0.0,
    annualization: int = 252,
) -> dict:
    """向量化回测核心，返回指标 dict。

    Args:
        nav: 基金单位净值序列（升序）。
        signals: 持仓信号序列（1=满仓, 0=空仓）。
        commission_bps: 手续费（基点，1bp=0.01%）。
        slippage_bps: 滑点（基点）。
        annualization: 年化交易日。

    Returns:
        dict(annual_return, sharpe, max_drawdown, win_rate, calmar)。
    """
    nav = nav.astype(float).sort_index()
    signals = signals.reindex(nav.index).fillna(0.0).astype(float)

    asset_returns = nav.pct_change()
    # 昨日信号决定今日持仓（避免未来函数）
    position = signals.shift(1).fillna(0.0)
    strat_returns = asset_returns * position

    # 换手：信号变化时产生成本（首日建仓也算一次换手）
    turnover = position.diff().abs().fillna(position.abs().iloc[0] if len(position) else 0.0)
    cost_per_turnover = (commission_bps + slippage_bps) / 10000.0
    strat_returns = strat_returns - turnover * cost_per_turnover

    # 净值曲线
    nav_curve = (1.0 + strat_returns).cumprod()

    n = len(nav)
    years = n / annualization if annualization > 0 else 0.0
    if n == 0:
        return _empty_metrics()

    total_return = float(nav_curve.iloc[-1] - 1.0)
    if years > 0:
        annual_return = (1.0 + total_return) ** (1.0 / years) - 1.0
    else:
        annual_return = total_return

    std = float(strat_returns.std())
    mean = float(strat_returns.mean())
    sharpe = mean / std * (annualization ** 0.5) if std > 0 else 0.0

    peak = nav_curve.cummax()
    drawdown = (nav_curve - peak) / peak
    max_dd = float(drawdown.min()) if len(drawdown) else 0.0

    calmar = annual_return / abs(max_dd) if abs(max_dd) > 1e-12 else 0.0

    nonzero = strat_returns[strat_returns != 0.0]
    win_rate = float((nonzero > 0).sum() / len(nonzero)) if len(nonzero) else 0.0

    return {
        "annual_return": float(annual_return),
        "sharpe": float(sharpe),
        "max_drawdown": float(max_dd),
        "win_rate": float(win_rate),
        "calmar": float(calmar),
    }


def _empty_metrics() -> dict:
    return {
        "annual_return": 0.0,
        "sharpe": 0.0,
        "max_drawdown": 0.0,
        "win_rate": 0.0,
        "calmar": 0.0,
    }


def _slice_trailing(nav: pd.Series, years: int, annualization: int) -> pd.Series:
    """取最近 years 年的净值（按行数近似）。"""
    if years <= 0:
        return nav
    take = years * annualization
    if len(nav) > take:
        return nav.iloc[-take:]
    return nav


class PandasBacktestRunner(BacktestRunner):
    """基于 pandas 向量化的回测引擎，同时支持快速扫描与精细回测。

    两档差异仅在成本参数：
    - 快速扫描：不计成本（commission_bps=slippage_bps=0）
    - 精细回测：含手续费 + 滑点（来自 arena.yaml）
    """

    def __init__(
        self,
        nav: pd.Series,
        *,
        fast_commission_bps: float = 0.0,
        fast_slippage_bps: float = 0.0,
        precise_commission_bps: float = 15.0,
        precise_slippage_bps: float = 5.0,
        annualization: int = 252,
    ) -> None:
        self._nav = nav.astype(float).sort_index()
        self._fast_commission = fast_commission_bps
        self._fast_slippage = fast_slippage_bps
        self._precise_commission = precise_commission_bps
        self._precise_slippage = precise_slippage_bps
        self._annualization = annualization

    def _backtest_one(
        self,
        strategy: Strategy,
        years: int,
        commission_bps: float,
        slippage_bps: float,
        precise: bool,
    ) -> BacktestResult:
        nav = _slice_trailing(self._nav, years, self._annualization)
        proto_cls = get_strategy_class(strategy.prototype_id)
        signals = proto_cls().generate(nav, strategy.params)
        metrics = vectorized_backtest(
            nav,
            signals,
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
            annualization=self._annualization,
        )
        backtest_years = round(len(nav) / self._annualization) if self._annualization else years
        return BacktestResult(
            strategy_id=strategy.strategy_id,
            backtest_years=backtest_years,
            precise=precise,
            **metrics,
        )

    def run_fast_scan(
        self, strategies: list[Strategy], years: int
    ) -> list[BacktestResult]:
        logger.info("快速扫描回测：{} 个策略 × {} 年", len(strategies), years)
        return [
            self._backtest_one(
                s, years, self._fast_commission, self._fast_slippage, precise=False
            )
            for s in strategies
        ]

    def run_precise(
        self, strategies: list[Strategy], years: int
    ) -> list[BacktestResult]:
        logger.info("精细回测：{} 个策略 × {} 年", len(strategies), years)
        return [
            self._backtest_one(
                s, years, self._precise_commission, self._precise_slippage, precise=True
            )
            for s in strategies
        ]
