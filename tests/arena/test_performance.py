"""T18: 性能测试 —— 回测向量化引擎在大批量策略下的性能。

回测不调真实网络/LLM，使用构造的 5 年净值序列。直接构造差异化策略对象，
绕过 LLM/去重，隔离回测引擎本身的性能特征。
"""
from __future__ import annotations

import time

import pytest

from src.arena.backtest.pandas_runner import PandasBacktestRunner
from src.arena.backtest.top_n import trigger_precise
from src.arena.models import Strategy
from src.arena.ranker import ArenaRanker
from tests.arena.conftest import make_nav


# 15 原型 × 多组参数 → 生成足够多彼此差异化的策略
_DISTINCT_SPECS = [
    ("趋势", "proto_ma_cross", {"fast": f, "slow": s}, "技术面", "月", 0.10, "Top10")
    for f in (5, 10, 15, 20) for s in (20, 30, 40, 60)
] + [
    ("趋势", "proto_macd", {"fast": f, "slow": s, "signal": 9}, "技术面", "双周", 0.05, "Top20")
    for f in (8, 12) for s in (20, 26)
] + [
    ("价值", "proto_4433", {"short_window": a, "mid_window": b, "long_window": c}, "基本面", "季", 0.20, "Top50")
    for a in (21, 42) for b in (63, 84) for c in (126, 189)
] + [
    ("低波", "proto_drawdown_recovery", {"threshold": t}, "技术面", "月", 0.05, "Top20")
    for t in (0.08, 0.12, 0.15)
] + [
    ("成长", "proto_momentum_rotation", {"window": w}, "技术面", "双周", 0.10, "Top10")
    for w in (20, 30, 40, 60)
] + [
    ("成长", "proto_bollinger_breakout", {"window": 20, "k": k}, "技术面", "周", 0.05, "Top5")
    for k in (1.5, 2.0, 2.5)
] + [
    ("逆向", "proto_rsi_reversal", {"period": p, "oversold": 30, "overbought": 70}, "技术面", "月", 0.10, "Top10")
    for p in (7, 14, 21)
] + [
    ("全球配置", "proto_dual_momentum", {"abs_window": a, "rel_window": r}, "技术+基本", "月", 0.15, "Top50")
    for a in (126, 252) for r in (21, 63)
] + [
    ("低波", "proto_dca", {}, "无择时", "季", 0.20, "Top50"),
    ("指数增强", "proto_low_vol", {}, "无择时", "季", 0.15, "Top20"),
    ("指数增强", "proto_risk_parity", {}, "无择时", "季", 0.20, "Top50"),
]


def _build_strategies(n: int) -> list[Strategy]:
    """构造 n 个彼此差异化的策略（覆盖不同原型+领域+参数）。"""
    out: list[Strategy] = []
    for i in range(n):
        d, pid, p, tl, freq, risk, conc = _DISTINCT_SPECS[i % len(_DISTINCT_SPECS)]
        # 用 index 微调使每个策略唯一（避免去重），但不影响性能
        params = dict(p)
        # 给数值参数加一个随 i 变化的微小扰动，保证向量互异
        params = {k: (v + (i % 7) * 0.001) for k, v in params.items()} or {}
        out.append(Strategy(
            strategy_id=f"perf_{i}",
            prototype_id=pid,
            domain=d,  # type: ignore[arg-type]
            params=params,
            timing_logic=tl,
            rebalance_freq=freq,
            risk_threshold=float(risk),
            concentration=conc,
            source_explanation="性能测试策略",
        ))
    return out


@pytest.mark.slow
class TestPerformance:
    def test_fast_scan_50_strategies_under_60s(self):
        nav = make_nav(252 * 5)
        strategies = _build_strategies(50)
        assert len(strategies) == 50

        runner = PandasBacktestRunner(nav)
        t0 = time.perf_counter()
        results = runner.run_fast_scan(strategies, years=5)
        elapsed = time.perf_counter() - t0

        assert len(results) == 50
        # 向量化回测应很快（宽松上限，CI 友好）
        assert elapsed < 60.0, f"快速扫描 50 策略耗时 {elapsed:.2f}s 超过 60s"

    def test_ranking_under_5s(self):
        nav = make_nav(252 * 5)
        strategies = _build_strategies(50)
        runner = PandasBacktestRunner(nav)
        results = runner.run_fast_scan(strategies, years=5)

        t0 = time.perf_counter()
        rankings = ArenaRanker().rank_by_domain(results, strategies)
        elapsed = time.perf_counter() - t0
        assert elapsed < 5.0
        assert len(rankings) > 0

    def test_precise_scan_top20_under_30s(self):
        nav = make_nav(252 * 5)
        strategies = _build_strategies(50)
        runner = PandasBacktestRunner(nav)
        fast = runner.run_fast_scan(strategies, years=5)

        t0 = time.perf_counter()
        precise = trigger_precise(fast, strategies, runner, years=5, top_n=20)
        elapsed = time.perf_counter() - t0
        assert elapsed < 30.0
        assert len(precise) == 20
