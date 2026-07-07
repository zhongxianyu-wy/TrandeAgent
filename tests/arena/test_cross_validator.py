"""T15: 双轨交叉验证测试。"""
from __future__ import annotations

import pytest

from src.arena.cross_validator import (
    backtest_to_monthly,
    cross_validate,
    cross_validate_batch,
)
from src.arena.models import BacktestResult, ForwardResult


def _bt(annual: float, sid: str = "s") -> BacktestResult:
    return BacktestResult(
        strategy_id=sid, annual_return=annual, sharpe=1.0,
        max_drawdown=-0.1, win_rate=0.5, calmar=1.0, backtest_years=5,
    )


def _fwd(ret: float, days: int, sid: str = "s") -> ForwardResult:
    return ForwardResult(strategy_id=sid, forward_days=days, forward_return=ret)


class TestMonthlyConversion:
    def test_zero(self):
        assert backtest_to_monthly(0.0) == 0.0

    def test_positive(self):
        # 年化 12% → 月化约 0.949%
        m = backtest_to_monthly(0.12)
        assert abs(m - ((1.12) ** (1 / 12) - 1)) < 1e-12


class TestCrossValidate:
    def test_close_values_not_suspicious(self):
        bt = _bt(0.12)
        fwd = _fwd(backtest_to_monthly(0.12), 30)
        cc = cross_validate(bt, fwd, threshold=0.2)
        assert cc.suspicious is False
        assert cc.relative_diff < 0.2

    def test_large_gap_suspicious(self):
        bt = _bt(0.12)
        fwd = _fwd(0.10, 30)  # 月化约0.95%，纸上10% → 差异巨大
        cc = cross_validate(bt, fwd, threshold=0.2)
        assert cc.suspicious is True

    def test_custom_threshold(self):
        bt = _bt(0.12)
        fwd = _fwd(backtest_to_monthly(0.15), 30)
        # 差异适中：5% 阈值触发，50% 不触发
        assert cross_validate(bt, fwd, threshold=0.05).suspicious is True
        assert cross_validate(bt, fwd, threshold=0.50).suspicious is False

    def test_zero_backtest_return_guard(self):
        bt = _bt(0.0)
        fwd = _fwd(0.0, 30)
        cc = cross_validate(bt, fwd)
        assert cc.suspicious is False  # 都为 0

    def test_batch(self):
        pairs = [(_bt(0.12, "a"), _fwd(0.10, 30, "a")),
                 (_bt(0.05, "b"), _fwd(backtest_to_monthly(0.05), 30, "b"))]
        results = cross_validate_batch(pairs, threshold=0.2)
        assert len(results) == 2
        assert results[0].suspicious is True
        assert results[1].suspicious is False

    def test_strategy_id_propagated(self):
        cc = cross_validate(_bt(0.1, "xyz"), _fwd(0.0, 30, "xyz"))
        assert cc.strategy_id == "xyz"
