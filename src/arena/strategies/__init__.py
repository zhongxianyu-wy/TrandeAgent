"""策略原型实现包（T08）。

对外暴露 :data:`PROTOTYPE_REGISTRY`、 :func:`get_strategy_class` 以及
:class:`StrategyBase`。
"""
from __future__ import annotations

from src.arena.strategies.base import StrategyBase
from src.arena.strategies.prototypes import (
    PROTOTYPE_REGISTRY,
    Strategy4433,
    StrategyBollingerBreakout,
    StrategyDCA,
    StrategyDrawdownRecovery,
    StrategyDualMomentum,
    StrategyGrid,
    StrategyLowVol,
    StrategyMACD,
    StrategyMACross,
    StrategyMeanReversion,
    StrategyMomentumRotation,
    StrategyPEDCA,
    StrategyRiskParity,
    StrategyRSIReversal,
    StrategyTurtle,
    get_strategy_class,
    list_prototype_ids,
)

__all__ = [
    "StrategyBase",
    "PROTOTYPE_REGISTRY",
    "get_strategy_class",
    "list_prototype_ids",
    "Strategy4433",
    "StrategyDualMomentum",
    "StrategyGrid",
    "StrategyDCA",
    "StrategyMACross",
    "StrategyMACD",
    "StrategyRSIReversal",
    "StrategyBollingerBreakout",
    "StrategyDrawdownRecovery",
    "StrategyPEDCA",
    "StrategyMomentumRotation",
    "StrategyLowVol",
    "StrategyTurtle",
    "StrategyMeanReversion",
    "StrategyRiskParity",
]
