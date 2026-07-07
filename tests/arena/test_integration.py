"""T17/T18: 集成测试 —— 端到端全流程（mock LLM，构造净值）。"""
from __future__ import annotations

from datetime import date

import pytest

from src.arena.pipeline import ArenaPipeline, BaseWriter, make_default_pipeline
from src.arena.cross_validator import cross_validate_batch
from src.arena.forward import DefaultForwardSimulator
from src.arena.generator import LLMStrategyGenerator
from src.arena.models import ArenaRanking
from src.arena.ranker import ArenaRanker
from tests.arena.conftest import valid_llm_strategy_payload


class RecordingBaseWriter:
    """记录写入调用的 BaseWriter 实现（验证接口预留）。"""

    def __init__(self) -> None:
        self.written: list[ArenaRanking] = []
        self.call_count = 0

    def write_rankings(self, rankings, strategies, results) -> None:
        self.written = list(rankings)
        self.call_count += 1


def _multi_domain_llm_payload() -> dict:
    """构造覆盖多个领域的合法 LLM 返回（数量 >= top_n 以触发精细回测）。"""
    specs = [
        ("趋势", "proto_ma_cross", {"fast": 10, "slow": 30}, "技术面"),
        ("趋势", "proto_macd", {}, "技术面"),
        ("趋势", "proto_turtle", {}, "技术面"),
        ("价值", "proto_4433", {}, "基本面"),
        ("价值", "proto_pe_dca", {}, "基本面"),
        ("低波", "proto_dca", {}, "无择时"),
        ("低波", "proto_drawdown_recovery", {"threshold": 0.12}, "技术面"),
        ("成长", "proto_momentum_rotation", {"window": 40}, "技术面"),
        ("成长", "proto_bollinger_breakout", {}, "技术面"),
        ("指数增强", "proto_risk_parity", {}, "无择时"),
    ]
    strategies = []
    for i, (d, pid, p, tl) in enumerate(specs):
        item = valid_llm_strategy_payload(
            sid=f"int_{i}", prototype_id=pid, domain=d, mind_model_id=None
        )
        item["params"] = p
        item["timing_logic"] = tl
        strategies.append(item)
    return {"strategies": strategies}


class TestEndToEnd:
    def test_full_pipeline(
        self, mock_llm_factory, nav, prototype_dicts, mind_model_dicts, dim_matrix, arena_config
    ):
        from src.arena.backtest.pandas_runner import PandasBacktestRunner

        gen = LLMStrategyGenerator(mock_llm_factory([_multi_domain_llm_payload()]))
        runner = PandasBacktestRunner(nav)
        pipeline = ArenaPipeline(
            generator=gen,
            runner=runner,
            ranker=ArenaRanker(top_per_domain=3),
            prototypes=prototype_dicts,
            mind_models=mind_model_dicts,
            dim_matrix=dim_matrix,
            fast_years=3,
            top_n_precise=5,
        )
        result = pipeline.run(count=10)
        assert len(result.strategies) == 10
        assert len(result.fast_results) == 10
        assert len(result.precise_results) == 5  # top_n_precise
        assert len(result.rankings) > 0
        # 每个排名领域 <= top_per_domain
        from collections import Counter
        per_domain = Counter(r.domain for r in result.rankings)
        assert all(c <= 3 for c in per_domain.values())
        # 所有策略可追溯到原型
        for s in result.strategies:
            assert s.prototype_id.startswith("proto_")

    def test_pipeline_with_base_writer(
        self, mock_llm_factory, nav, prototype_dicts, mind_model_dicts, dim_matrix
    ):
        from src.arena.backtest.pandas_runner import PandasBacktestRunner

        writer = RecordingBaseWriter()
        gen = LLMStrategyGenerator(mock_llm_factory([_multi_domain_llm_payload()]))
        runner = PandasBacktestRunner(nav)
        pipeline = ArenaPipeline(
            generator=gen,
            runner=runner,
            base_writer=writer,
            prototypes=prototype_dicts,
            mind_models=mind_model_dicts,
            dim_matrix=dim_matrix,
            fast_years=3,
            top_n_precise=3,
        )
        result = pipeline.run(count=10, write_base=True)
        assert writer.call_count == 1
        assert len(writer.written) == len(result.rankings)

    def test_pipeline_skip_base_when_no_writer(
        self, mock_llm_factory, nav, prototype_dicts, mind_model_dicts, dim_matrix
    ):
        from src.arena.backtest.pandas_runner import PandasBacktestRunner

        gen = LLMStrategyGenerator(mock_llm_factory([_multi_domain_llm_payload()]))
        runner = PandasBacktestRunner(nav)
        pipeline = ArenaPipeline(
            generator=gen,
            runner=runner,
            prototypes=prototype_dicts,
            mind_models=mind_model_dicts,
            dim_matrix=dim_matrix,
            fast_years=2,
            top_n_precise=3,
        )
        # 无 writer，write_base=True 也不报错
        result = pipeline.run(count=10, write_base=True)
        assert len(result.strategies) == 10

    def test_make_default_pipeline_factory(
        self, mock_llm_factory, nav, arena_config
    ):
        llm = mock_llm_factory([{"strategies": []}])
        pipeline = make_default_pipeline(nav, llm, config=arena_config)
        assert pipeline is not None
        assert pipeline._fast_years == arena_config["backtest"]["fast_years"]


class TestDualTrackCrossValidation:
    """T15 集成：回测 + 纸上双轨交叉验证。"""

    def test_cross_validate_after_forward(
        self, mock_llm_factory, nav, prototype_dicts, mind_model_dicts, dim_matrix
    ):
        from src.arena.backtest.pandas_runner import PandasBacktestRunner

        gen = LLMStrategyGenerator(mock_llm_factory([_multi_domain_llm_payload()]))
        strategies = gen.generate(10, prototype_dicts, mind_model_dicts, dim_matrix)
        runner = PandasBacktestRunner(nav)
        backtests = runner.run_fast_scan(strategies, years=3)

        sim = DefaultForwardSimulator(strategies, nav, qualified_days=30)
        sim.run(30)
        forwards = sim.get_all_forward_results()

        pairs = [
            (bt, next(f for f in forwards if f.strategy_id == bt.strategy_id))
            for bt in backtests
        ]
        checks = cross_validate_batch(pairs, threshold=0.2)
        assert len(checks) == len(strategies)
        # 所有 check 都有明确的 suspicious 标志
        assert all(isinstance(c.suspicious, bool) for c in checks)


class TestQualifiedGate:
    """集成：不满 30 天不能进 Top-5（由 ForwardSimulator 判定）。"""

    def test_under_30_days_not_qualified(self, nav, strategy):
        sim = DefaultForwardSimulator([strategy], nav, qualified_days=30)
        sim.run(25)
        assert not sim.is_qualified(strategy.strategy_id)
        assert sim.get_forward_result(strategy.strategy_id).is_qualified is False
