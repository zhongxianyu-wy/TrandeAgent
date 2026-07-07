"""竞技场集成入口（T17）。

编排"生成 → 快速回测 → Top-N 精细回测 → 领域排名"全流程，并预留写入飞书
Base 的接口（:class:`BaseWriter` 协议）。实际写 Base 由 #2 feishu-io 完成，
此处仅定义契约与可选调用，避免与 feishu 耦合。
"""
from __future__ import annotations

from datetime import date
from typing import Protocol

from loguru import logger

import pandas as pd

from src.arena.backtest.pandas_runner import PandasBacktestRunner
from src.arena.backtest.top_n import trigger_precise
from src.arena.generator import LLMStrategyGenerator
from src.arena.models import (
    ArenaRanking,
    ArenaRunResult,
    BacktestResult,
    Strategy,
)
from src.arena.ranker import ArenaRanker


class BaseWriter(Protocol):
    """写入飞书 Base "策略竞技场"表接口（由 #2 feishu-io 实现）。"""

    def write_rankings(
        self,
        rankings: list[ArenaRanking],
        strategies: list[Strategy],
        results: list[BacktestResult],
    ) -> None:
        ...


class ArenaPipeline:
    """竞技场主流程编排器。

    串联生成器、回测引擎、排名器；可选触发纸上模拟与 Base 写入。
    """

    def __init__(
        self,
        *,
        generator: LLMStrategyGenerator,
        runner: PandasBacktestRunner,
        ranker: ArenaRanker | None = None,
        base_writer: BaseWriter | None = None,
        prototypes: list[dict] | None = None,
        mind_models: list[dict] | None = None,
        dim_matrix: dict | None = None,
        fast_years: int = 5,
        top_n_precise: int = 20,
    ) -> None:
        self._generator = generator
        self._runner = runner
        self._ranker = ranker or ArenaRanker()
        self._base_writer = base_writer
        self._prototypes = prototypes or []
        self._mind_models = mind_models or []
        self._dim_matrix = dim_matrix or {}
        self._fast_years = fast_years
        self._top_n_precise = top_n_precise

    def run(self, *, count: int, write_base: bool = False) -> ArenaRunResult:
        """执行完整竞技场流程。

        Args:
            count: 目标生成策略数。
            write_base: 是否写入飞书 Base（需在构造时提供 base_writer）。
        """
        strategies = self._generator.generate(
            count,
            self._prototypes,
            self._mind_models,
            self._dim_matrix,
        )
        logger.info("竞技场：生成 {} 个策略", len(strategies))

        fast = self._runner.run_fast_scan(strategies, self._fast_years)
        precise = trigger_precise(
            fast,
            strategies,
            self._runner,
            years=self._fast_years,
            top_n=self._top_n_precise,
        )

        # 排名以精细回测结果为准；若无精细回测则退化为快速结果
        scoring_results = precise or fast
        rankings = self._ranker.rank_by_domain(scoring_results, strategies)

        if write_base and self._base_writer is not None:
            self._base_writer.write_rankings(rankings, strategies, scoring_results)
            logger.info("竞技场：已写入飞书 Base（{} 条排名）", len(rankings))

        return ArenaRunResult(
            strategies=strategies,
            fast_results=fast,
            precise_results=precise,
            rankings=rankings,
        )


def make_default_pipeline(
    nav: pd.Series,
    llm_client,
    *,
    config: dict | None = None,
    deduplicator=None,
    base_writer: BaseWriter | None = None,
) -> ArenaPipeline:
    """根据 arena.yaml 配置构建默认 ArenaPipeline（便捷工厂）。"""
    if config is None:
        from src.arena.mind_models.loader import load_arena_config

        config = load_arena_config()

    bt_cfg = config.get("backtest", {})
    gen_cfg = config.get("generation", {})
    rank_cfg = config.get("ranking", {})
    runner = PandasBacktestRunner(
        nav,
        fast_commission_bps=bt_cfg.get("fast_commission_bps", 0.0),
        fast_slippage_bps=bt_cfg.get("fast_slippage_bps", 0.0),
        precise_commission_bps=bt_cfg.get("precise_commission_bps", 15.0),
        precise_slippage_bps=bt_cfg.get("precise_slippage_bps", 5.0),
        annualization=bt_cfg.get("annualization", 252),
    )
    generator = LLMStrategyGenerator(
        llm_client,
        deduplicator=deduplicator,
        system_hint=gen_cfg.get("llm_system_hint"),
    )
    ranker = ArenaRanker(
        weights=rank_cfg.get("weights"),
        top_per_domain=rank_cfg.get("top_per_domain", 5),
    )
    return ArenaPipeline(
        generator=generator,
        runner=runner,
        ranker=ranker,
        base_writer=base_writer,
        fast_years=bt_cfg.get("fast_years", 5),
        top_n_precise=bt_cfg.get("top_n_precise", 20),
    )
