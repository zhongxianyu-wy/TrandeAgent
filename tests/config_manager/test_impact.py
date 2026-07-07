"""T05/T06/T07：影响范围分析测试。

覆盖观察池 / 筛选规则 / 信号规则 / 竞技场 四类变更检测。
"""
from __future__ import annotations

import pytest

from src.config_manager.impact import (
    _arena_impact,
    _diff_named_rules,
    _diff_sets,
    _pool_impact,
    _screener_impact,
    _signal_impact,
    analyze_impact,
)
from src.config_manager.schema import ArenaSection, ChangeImpact
from src.screener.models import Rule as ScreenerRule
from src.signal.models import SignalRule

from tests.config_manager.conftest import make_config, make_screener_rule, make_signal_rule


class TestDiffHelpers:
    def test_diff_sets(self):
        added, removed = _diff_sets({"a", "b"}, {"b", "c"})
        assert added == ["c"]
        assert removed == ["a"]

    def test_diff_sets_no_change(self):
        added, removed = _diff_sets({"a"}, {"a"})
        assert added == []
        assert removed == []

    def test_diff_named_rules_added_removed(self):
        old = [make_screener_rule(name="r1"), make_screener_rule(name="r2")]
        new = [make_screener_rule(name="r2"), make_screener_rule(name="r3")]
        added, removed, modified = _diff_named_rules(old, new)
        assert added == ["r3"]
        assert removed == ["r1"]
        assert modified == []

    def test_diff_named_rules_modified(self):
        old = [make_screener_rule(name="r1", value=1.0)]
        new = [make_screener_rule(name="r1", value=2.0)]
        added, removed, modified = _diff_named_rules(old, new)
        assert added == []
        assert removed == []
        assert modified == ["r1"]


class TestPoolImpact:
    def test_pool_change(self):
        old = make_config(pool=["001", "002"])
        new = make_config(pool=["002", "003"])
        impact = _pool_impact(old, new)
        assert impact is not None
        assert impact.change_type == "pool"
        assert impact.added == ["003"]
        assert impact.removed == ["001"]
        assert "001" in impact.affected_funds
        assert "003" in impact.affected_funds

    def test_no_change_returns_none(self):
        old = make_config(pool=["001"])
        new = make_config(pool=["001"])
        assert _pool_impact(old, new) is None


class TestScreenerImpact:
    def test_screener_added(self):
        old = make_config(screener=[make_screener_rule(name="r1")])
        new = make_config(screener=[make_screener_rule(name="r1"), make_screener_rule(name="r2")])
        impact = _screener_impact(old, new)
        assert impact is not None
        assert impact.change_type == "screener"
        assert "r2" in impact.added

    def test_screener_modified(self):
        old = make_config(screener=[make_screener_rule(name="r1", value=1.0)])
        new = make_config(screener=[make_screener_rule(name="r1", value=5.0)])
        impact = _screener_impact(old, new)
        assert impact is not None
        assert impact.requires_backtest_rerun is False

    def test_screener_removed(self):
        old = make_config(screener=[make_screener_rule(name="r1"), make_screener_rule(name="r2")])
        new = make_config(screener=[make_screener_rule(name="r1")])
        impact = _screener_impact(old, new)
        assert impact is not None
        assert "r2" in impact.removed

    def test_no_change_returns_none(self):
        old = make_config(screener=[make_screener_rule(name="r1")])
        new = make_config(screener=[make_screener_rule(name="r1")])
        assert _screener_impact(old, new) is None

    def test_affected_funds_from_pool(self):
        old = make_config(pool=["001", "002"], screener=[make_screener_rule(name="r1")])
        new = make_config(pool=["001", "002"], screener=[make_screener_rule(name="r1", value=9.0)])
        impact = _screener_impact(old, new)
        assert "001" in impact.affected_funds


class TestSignalImpact:
    def test_signal_added(self):
        old = make_config(signals=[make_signal_rule(name="s1")])
        new = make_config(signals=[make_signal_rule(name="s1"), make_signal_rule(name="s2")])
        impact = _signal_impact(old, new)
        assert impact is not None
        assert impact.change_type == "signal"
        assert "s2" in impact.added

    def test_signal_modified(self):
        old = make_config(signals=[make_signal_rule(name="s1", threshold=30)])
        new = make_config(signals=[make_signal_rule(name="s1", threshold=50)])
        impact = _signal_impact(old, new)
        assert impact is not None

    def test_no_change_returns_none(self):
        old = make_config(signals=[make_signal_rule(name="s1")])
        new = make_config(signals=[make_signal_rule(name="s1")])
        assert _signal_impact(old, new) is None


class TestArenaImpact:
    def test_arena_change_requires_rerun(self):
        old = make_config(arena=ArenaSection(strategy_count=100))
        new = make_config(arena=ArenaSection(strategy_count=200))
        impact = _arena_impact(old, new)
        assert impact is not None
        assert impact.change_type == "arena"
        assert impact.requires_backtest_rerun is True
        assert "strategy_count" in impact.added

    def test_arena_disabled(self):
        old = make_config(arena=ArenaSection(enabled=True))
        new = make_config(arena=ArenaSection(enabled=False))
        impact = _arena_impact(old, new)
        assert impact is not None
        assert impact.requires_backtest_rerun is True

    def test_no_change_returns_none(self):
        old = make_config(arena=ArenaSection())
        new = make_config(arena=ArenaSection())
        assert _arena_impact(old, new) is None


class TestAnalyzeImpact:
    def test_no_changes(self):
        cfg = make_config()
        assert analyze_impact(cfg, cfg) == []

    def test_multiple_changes(self):
        old = make_config(
            pool=["001"],
            screener=[make_screener_rule(name="r1")],
            arena=ArenaSection(strategy_count=100),
        )
        new = make_config(
            pool=["001", "002"],
            screener=[make_screener_rule(name="r1"), make_screener_rule(name="r2")],
            arena=ArenaSection(strategy_count=200),
        )
        impacts = analyze_impact(old, new)
        types = [i.change_type for i in impacts]
        assert "pool" in types
        assert "screener" in types
        assert "arena" in types

    def test_returns_list_of_changeimpact(self):
        old = make_config(pool=["001"])
        new = make_config(pool=["002"])
        impacts = analyze_impact(old, new)
        assert all(isinstance(i, ChangeImpact) for i in impacts)
