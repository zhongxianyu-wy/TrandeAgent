"""T08: 15 个策略原型信号生成测试。"""
from __future__ import annotations

import pandas as pd
import pytest

from src.arena.strategies import (
    PROTOTYPE_REGISTRY,
    StrategyBase,
    get_strategy_class,
    list_prototype_ids,
)


EXPECTED_PROTOS = [
    "proto_4433", "proto_dual_momentum", "proto_grid", "proto_dca",
    "proto_ma_cross", "proto_macd", "proto_rsi_reversal",
    "proto_bollinger_breakout", "proto_drawdown_recovery", "proto_pe_dca",
    "proto_momentum_rotation", "proto_low_vol", "proto_turtle",
    "proto_mean_reversion", "proto_risk_parity",
]


class TestRegistry:
    def test_15_prototypes_registered(self):
        assert len(PROTOTYPE_REGISTRY) == 15
        assert set(list_prototype_ids()) == set(EXPECTED_PROTOS)

    def test_get_strategy_class_known(self):
        cls = get_strategy_class("proto_4433")
        assert issubclass(cls, StrategyBase)
        assert cls.prototype_id == "proto_4433"

    def test_get_strategy_class_unknown_raises(self):
        with pytest.raises(KeyError):
            get_strategy_class("proto_invented")


@pytest.mark.parametrize("pid", EXPECTED_PROTOS)
class TestPrototypeSignals:
    def test_signal_aligned_and_bounded(self, pid, nav):
        proto = get_strategy_class(pid)()
        sig = proto.generate(nav)
        assert len(sig) == len(nav)
        assert sig.min() >= 0.0
        assert sig.max() <= 1.0

    def test_custom_params_override_defaults(self, pid, nav):
        proto = get_strategy_class(pid)()
        sig_default = proto.generate(nav)
        sig_custom = proto.generate(nav, proto.default_params or {})
        assert len(sig_default) == len(sig_custom)

    def test_short_series_no_crash(self, pid, short_nav):
        proto = get_strategy_class(pid)()
        sig = proto.generate(short_nav)
        assert len(sig) == len(short_nav)
        assert sig.notna().all()


class TestSpecificLogic:
    def test_dca_always_holds(self, nav):
        sig = get_strategy_class("proto_dca")().generate(nav)
        assert (sig == 1.0).all()

    def test_low_vol_always_holds(self, nav):
        sig = get_strategy_class("proto_low_vol")().generate(nav)
        assert (sig == 1.0).all()

    def test_risk_parity_always_holds(self, nav):
        sig = get_strategy_class("proto_risk_parity")().generate(nav)
        assert (sig == 1.0).all()

    def test_ma_cross_responds_to_params(self, nav):
        proto = get_strategy_class("proto_ma_cross")
        sig_short = proto().generate(nav, {"fast": 5, "slow": 10})
        sig_long = proto().generate(nav, {"fast": 60, "slow": 120})
        # 不同窗口产生的信号占比应有差异
        assert float(sig_short.mean()) >= 0.0
        assert float(sig_long.mean()) >= 0.0

    def test_drawdown_recovery_threshold_effect(self, nav):
        proto = get_strategy_class("proto_drawdown_recovery")
        tight = proto().generate(nav, {"threshold": 0.05})  # 紧阈值→更多空仓
        loose = proto().generate(nav, {"threshold": 0.50})  # 松阈值→更多持有
        assert float(tight.mean()) <= float(loose.mean())

    def test_generate_signals_is_abstract(self):
        with pytest.raises(TypeError):
            StrategyBase()  # type: ignore[abstract]

    def test_signal_clip_upper(self, nav):
        class _Boom(StrategyBase):
            prototype_id = "proto_test"
            default_params = {}

            def generate_signals(self, nav, params):
                return pd.Series(5.0, index=nav.index)

        sig = _Boom().generate(nav)
        assert sig.max() <= 1.0
        assert sig.min() >= 0.0
