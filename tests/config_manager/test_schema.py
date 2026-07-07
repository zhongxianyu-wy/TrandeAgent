"""T01：AppConfig + ArenaSection + ChangeImpact schema 测试。"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.config_manager.schema import AppConfig, ArenaSection, ChangeImpact
from src.screener.models import Rule as ScreenerRule
from src.signal.models import SignalRule

from tests.config_manager.conftest import make_config, make_screener_rule, make_signal_rule


class TestArenaSection:
    def test_defaults(self):
        a = ArenaSection()
        assert a.enabled is True
        assert a.strategy_count == 100
        assert a.backtest_years == 5
        assert a.top_n_per_domain == 5

    def test_custom_values(self):
        a = ArenaSection(enabled=False, strategy_count=50, backtest_years=3, top_n_per_domain=3)
        assert a.enabled is False
        assert a.strategy_count == 50

    @pytest.mark.parametrize("field", ["strategy_count", "backtest_years", "top_n_per_domain"])
    def test_must_be_positive(self, field):
        with pytest.raises(ValidationError):
            ArenaSection(**{field: 0})


class TestAppConfig:
    def test_defaults(self):
        cfg = AppConfig()
        assert cfg.observation_pool == []
        assert cfg.screener_rules == []
        assert cfg.signal_rules == []
        assert isinstance(cfg.arena, ArenaSection)

    def test_full_config(self):
        cfg = make_config()
        assert cfg.observation_pool == ["000001", "000002"]
        assert len(cfg.screener_rules) == 1
        assert len(cfg.signal_rules) == 1

    def test_pool_dedup_preserves_order(self):
        cfg = AppConfig(observation_pool=["003", "001", "003", "002", "001"])
        assert cfg.observation_pool == ["003", "001", "002"]

    def test_invalid_screener_op_rejected(self):
        with pytest.raises(ValidationError):
            AppConfig(screener_rules=[ScreenerRule(name="x", field="f", op="!=", value=1)])

    def test_invalid_signal_category_rejected(self):
        with pytest.raises(ValidationError):
            AppConfig(signal_rules=[SignalRule(name="x", category="bad", indicator="rsi", operator="above")])

    def test_invalid_signal_weight_rejected(self):
        with pytest.raises(ValidationError):
            AppConfig(signal_rules=[SignalRule(name="x", category="technical", indicator="rsi", operator="above", weight=-1)])


class TestChangeImpact:
    def test_defaults(self):
        ci = ChangeImpact(change_type="screener")
        assert ci.change_type == "screener"
        assert ci.added == []
        assert ci.removed == []
        assert ci.affected_funds == []
        assert ci.requires_backtest_rerun is False
        assert ci.summary == ""

    def test_invalid_change_type(self):
        with pytest.raises(ValidationError):
            ChangeImpact(change_type="unknown")
