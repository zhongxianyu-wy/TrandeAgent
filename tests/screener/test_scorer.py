"""T08：综合得分（加权打分）测试。"""
from __future__ import annotations

import pytest

from src.screener.models import Rule, ScreenerConfig
from src.screener.scorer import score_fund


def _config(weights=None):
    return ScreenerConfig(
        rules=[Rule(name="a", field="sharpe", op=">=", value=1.0)],
        weights=weights or {},
    )


class TestScoreFund:
    def test_empty_matched(self):
        assert score_fund([], _config()) == 0.0

    def test_default_weight_one(self):
        # 缺省权重 1.0
        assert score_fund(["a"], _config()) == 1.0

    def test_explicit_weights(self):
        cfg = _config(weights={"a": 2.5})
        assert score_fund(["a"], cfg) == 2.5

    def test_sum_weights(self):
        cfg = ScreenerConfig(
            rules=[
                Rule(name="a", field="x", op=">=", value=1),
                Rule(name="b", field="y", op=">=", value=1),
                Rule(name="c", field="z", op=">=", value=1),
            ],
            weights={"a": 1.0, "b": 1.5, "c": 2.0},
        )
        # 命中 a 与 c → 1.0 + 2.0
        assert score_fund(["a", "c"], cfg) == pytest.approx(3.0)

    def test_unknown_rule_uses_default(self):
        # 未在 weights 中的规则名仍按默认 1.0 计
        cfg = _config(weights={})
        assert score_fund(["not_in_weights"], cfg) == 1.0
