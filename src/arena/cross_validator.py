"""双轨交叉验证（T15）。

比较"历史回测年化收益"与"纸上模拟当期收益"，相对差异 > 阈值（默认 20%）
则标记可疑（回测过拟合信号）。
"""
from __future__ import annotations

from src.arena.models import BacktestResult, CrossCheck, ForwardResult


def backtest_to_monthly(annual_return: float) -> float:
    """年化收益转月化收益（复利）。"""
    return (1.0 + annual_return) ** (1.0 / 12.0) - 1.0


def cross_validate(
    backtest: BacktestResult,
    forward: ForwardResult,
    *,
    threshold: float = 0.2,
) -> CrossCheck:
    """对单策略做双轨交叉验证。

    Args:
        backtest: 历史回测结果。
        forward: 纸上模拟结果。
        threshold: 可疑相对差异阈值，默认 0.2（20%）。

    Returns:
        CrossCheck，suspicious=True 表示回测与纸上差异过大。
    """
    bt_monthly = backtest_to_monthly(backtest.annual_return)
    denom = abs(bt_monthly)
    if denom < 1e-9:
        # 回测月化≈0 时，用纸上绝对收益是否显著判断
        denom = 1.0
    relative_diff = abs(forward.forward_return - bt_monthly) / denom
    return CrossCheck(
        strategy_id=backtest.strategy_id,
        backtest_monthly_return=bt_monthly,
        forward_return=forward.forward_return,
        relative_diff=float(relative_diff),
        suspicious=relative_diff > threshold,
    )


def cross_validate_batch(
    pairs: list[tuple[BacktestResult, ForwardResult]],
    *,
    threshold: float = 0.2,
) -> list[CrossCheck]:
    """批量交叉验证。"""
    return [cross_validate(bt, fwd, threshold=threshold) for bt, fwd in pairs]
