"""T07: cosine 去重测试。"""
from __future__ import annotations

import numpy as np
import pytest

from src.arena.deduplicator import (
    CONCENTRATIONS,
    CosineDeduplicator,
    cosine_distance,
    strategy_to_vector,
    vector_length,
)
from tests.arena.conftest import make_strategy


class TestCosineDistance:
    def test_identical_vectors_zero_distance(self):
        a = np.array([1.0, 2.0, 3.0])
        assert cosine_distance(a, a) == pytest.approx(0.0, abs=1e-12)

    def test_orthogonal_vectors_distance_one(self):
        a = np.array([1.0, 0.0])
        b = np.array([0.0, 1.0])
        assert cosine_distance(a, b) == pytest.approx(1.0, abs=1e-12)

    def test_opposite_vectors_distance_two(self):
        a = np.array([1.0, 0.0])
        b = np.array([-1.0, 0.0])
        assert cosine_distance(a, b) == pytest.approx(2.0, abs=1e-12)

    def test_zero_vector_distance_one(self):
        a = np.array([0.0, 0.0])
        b = np.array([1.0, 1.0])
        assert cosine_distance(a, b) == 1.0


class TestStrategyVector:
    def test_vector_fixed_length(self, strategy):
        v = strategy_to_vector(strategy)
        assert v.ndim == 1
        # one-hot(15+8+4+4+4) + risk(1) + PARAM_SCHEMA(19) = 55
        assert len(v) == vector_length()
        assert len(v) == 55

    def test_identical_strategies_zero_distance(self):
        s1 = make_strategy(strategy_id="a")
        s2 = make_strategy(strategy_id="b")
        d = CosineDeduplicator.pairwise_distance(s1, s2)
        assert d == pytest.approx(0.0, abs=1e-9)


class TestDeduplicator:
    def test_keeps_one_of_identical(self):
        dupes = [make_strategy(strategy_id=f"a{i}") for i in range(5)]
        kept = CosineDeduplicator().deduplicate(dupes, threshold=0.1)
        assert len(kept) == 1
        assert kept[0].strategy_id == "a0"  # 保留首个

    def test_distinct_strategies_all_kept(self):
        s1 = make_strategy(strategy_id="x", domain="趋势", timing_logic="技术面",
                           rebalance_freq="月", risk_threshold=0.05, concentration="Top5")
        s2 = make_strategy(strategy_id="y", domain="价值", timing_logic="基本面",
                           rebalance_freq="季", risk_threshold=0.20, concentration="Top50")
        kept = CosineDeduplicator().deduplicate([s1, s2], threshold=0.1)
        assert len(kept) == 2

    def test_threshold_zero_keeps_all_distinct(self):
        items = []
        for d in ["趋势", "价值", "低波"]:
            items.append(make_strategy(strategy_id=d, domain=d))
        # threshold=0 仅剔除完全相同
        kept = CosineDeduplicator().deduplicate(items, threshold=0.0)
        assert len(kept) == 3

    def test_negative_threshold_rejected(self):
        with pytest.raises(ValueError):
            CosineDeduplicator().deduplicate([], threshold=-0.1)

    def test_empty_input(self):
        assert CosineDeduplicator().deduplicate([]) == []

    def test_partial_duplication(self):
        base = make_strategy(strategy_id="b")
        same = make_strategy(strategy_id="s")  # 与 base 完全相同
        diff = make_strategy(
            strategy_id="d", domain="价值", timing_logic="基本面",
            rebalance_freq="季", risk_threshold=0.20, concentration="Top50",
        )
        kept = CosineDeduplicator().deduplicate([base, same, diff], threshold=0.1)
        ids = {s.strategy_id for s in kept}
        assert ids == {"b", "d"}
