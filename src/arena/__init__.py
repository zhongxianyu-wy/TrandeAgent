"""策略竞技场（Feature #8 strategy-arena）—— 核心创新模块。

基于 15 个策略原型 + 8 位投资大师心智模型，LLM 在差异维度矩阵约束下生成
差异化策略；纯 pandas 向量化回测 + 每日纸上模拟（双轨并行）；按 8 个投资
风格领域分组排名 Top-5。
"""
from __future__ import annotations

from src.arena.backtest.pandas_runner import (
    PandasBacktestRunner,
    vectorized_backtest,
)
from src.arena.backtest.runner import BacktestRunner
from src.arena.backtest.top_n import select_top_for_precise, trigger_precise
from src.arena.cross_validator import cross_validate, cross_validate_batch
from src.arena.deduplicator import CosineDeduplicator, cosine_distance, strategy_to_vector
from src.arena.forward import DefaultForwardSimulator, ForwardSimulator
from src.arena.generator import LLMStrategyGenerator, StrategyGenerator
from src.arena.models import (
    DOMAINS,
    ArenaRanking,
    ArenaRunResult,
    BacktestResult,
    CrossCheck,
    Domain,
    ForwardResult,
    Strategy,
)
from src.arena.pipeline import ArenaPipeline, BaseWriter, make_default_pipeline
from src.arena.ranker import ArenaRanker

__all__ = [
    "Domain",
    "DOMAINS",
    "Strategy",
    "BacktestResult",
    "ForwardResult",
    "ArenaRanking",
    "CrossCheck",
    "ArenaRunResult",
    "StrategyGenerator",
    "LLMStrategyGenerator",
    "CosineDeduplicator",
    "cosine_distance",
    "strategy_to_vector",
    "BacktestRunner",
    "PandasBacktestRunner",
    "vectorized_backtest",
    "select_top_for_precise",
    "trigger_precise",
    "ForwardSimulator",
    "DefaultForwardSimulator",
    "ArenaRanker",
    "cross_validate",
    "cross_validate_batch",
    "ArenaPipeline",
    "BaseWriter",
    "make_default_pipeline",
]
