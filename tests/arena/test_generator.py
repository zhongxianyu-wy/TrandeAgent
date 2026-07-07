"""T05/T06: 策略生成器测试（含防幻觉校验）。"""
from __future__ import annotations

import pytest

from src.arena.generator import LLMStrategyGenerator, StrategyGenerator
from tests.arena.conftest import valid_llm_strategy_payload


class TestGeneratorAbstraction:
    def test_is_strategy_generator(self, mock_llm_factory):
        gen = LLMStrategyGenerator(mock_llm_factory([]))
        assert isinstance(gen, StrategyGenerator)

    def test_generate_zero_count(self, mock_llm_factory, prototype_dicts, mind_model_dicts, dim_matrix):
        gen = LLMStrategyGenerator(mock_llm_factory([{"strategies": []}]))
        assert gen.generate(0, prototype_dicts, mind_model_dicts, dim_matrix) == []


class TestGenerationValidation:
    def test_valid_strategies_generated(
        self, mock_llm_factory, prototype_dicts, mind_model_dicts, dim_matrix
    ):
        payload = {
            "strategies": [
                valid_llm_strategy_payload(sid="g1", prototype_id="proto_ma_cross", domain="趋势"),
                valid_llm_strategy_payload(sid="g2", prototype_id="proto_4433", domain="价值", mind_model_id="mind_graham"),
                valid_llm_strategy_payload(sid="g3", prototype_id="proto_dca", domain="低波", mind_model_id=None),
            ]
        }
        gen = LLMStrategyGenerator(mock_llm_factory([payload]))
        strategies = gen.generate(3, prototype_dicts, mind_model_dicts, dim_matrix)
        assert len(strategies) == 3
        ids = {s.strategy_id for s in strategies}
        assert ids == {"g1", "g2", "g3"}
        # 每个策略可追溯到原型
        for s in strategies:
            assert s.prototype_id.startswith("proto_")
            assert s.domain in dim_matrix["domains"]

    def test_dedup_applied_post_generation(
        self, mock_llm_factory, prototype_dicts, mind_model_dicts, dim_matrix
    ):
        # 三个完全相同的策略 → 去重后应只剩 1 个
        same = valid_llm_strategy_payload(sid="dup", prototype_id="proto_ma_cross", domain="趋势")
        payload = {"strategies": [same, same.model_copy() if hasattr(same, "model_copy") else dict(same), dict(same)]}
        gen = LLMStrategyGenerator(mock_llm_factory([payload]))
        strategies = gen.generate(3, prototype_dicts, mind_model_dicts, dim_matrix)
        assert len(strategies) == 1

    def test_empty_llm_response(self, mock_llm_factory, prototype_dicts, mind_model_dicts, dim_matrix):
        gen = LLMStrategyGenerator(mock_llm_factory([{}]))
        assert gen.generate(5, prototype_dicts, mind_model_dicts, dim_matrix) == []

    def test_non_dict_response_returns_empty(
        self, mock_llm_factory, prototype_dicts, mind_model_dicts, dim_matrix
    ):
        gen = LLMStrategyGenerator(mock_llm_factory(["not a dict"]))
        assert gen.generate(2, prototype_dicts, mind_model_dicts, dim_matrix) == []


class TestAntiHallucination:
    """防幻觉：LLM 凭空发明的原型/大师/字段必须被拒绝。"""

    def test_invented_prototype_rejected(
        self, mock_llm_factory, prototype_dicts, mind_model_dicts, dim_matrix
    ):
        payload = {"strategies": [valid_llm_strategy_payload(invented_proto=True)]}
        gen = LLMStrategyGenerator(mock_llm_factory([payload]))
        result = gen.generate(1, prototype_dicts, mind_model_dicts, dim_matrix)
        assert result == []  # 凭空发明的原型被剔除

    def test_invented_mind_model_rejected(
        self, mock_llm_factory, prototype_dicts, mind_model_dicts, dim_matrix
    ):
        payload = {"strategies": [valid_llm_strategy_payload(invented_mind=True)]}
        gen = LLMStrategyGenerator(mock_llm_factory([payload]))
        result = gen.generate(1, prototype_dicts, mind_model_dicts, dim_matrix)
        assert result == []

    def test_domain_not_in_prototype_allowed_domains_rejected(
        self, mock_llm_factory, prototype_dicts, mind_model_dicts, dim_matrix
    ):
        # proto_ma_cross 合法领域 = [趋势, 指数增强]，给个"红利"应被拒
        payload = {"strategies": [valid_llm_strategy_payload(prototype_id="proto_ma_cross", domain="红利")]}
        gen = LLMStrategyGenerator(mock_llm_factory([payload]))
        result = gen.generate(1, prototype_dicts, mind_model_dicts, dim_matrix)
        assert result == []

    def test_params_outside_template_rejected(
        self, mock_llm_factory, prototype_dicts, mind_model_dicts, dim_matrix
    ):
        payload = {"strategies": [valid_llm_strategy_payload(extra_field=True)]}
        gen = LLMStrategyGenerator(mock_llm_factory([payload]))
        result = gen.generate(1, prototype_dicts, mind_model_dicts, dim_matrix)
        assert result == []

    def test_invalid_dim_axis_rejected(
        self, mock_llm_factory, prototype_dicts, mind_model_dicts, dim_matrix
    ):
        # timing_logic 不在矩阵内
        d = valid_llm_strategy_payload()
        d["timing_logic"] = "玄学面"
        payload = {"strategies": [d]}
        gen = LLMStrategyGenerator(mock_llm_factory([payload]))
        result = gen.generate(1, prototype_dicts, mind_model_dicts, dim_matrix)
        assert result == []

    def test_mind_model_reference_must_be_real(
        self, mock_llm_factory, prototype_dicts, mind_model_dicts, dim_matrix
    ):
        # mind_buffett 是真实大师，应通过；这里验证合法引用可保留
        payload = {"strategies": [
            valid_llm_strategy_payload(mind_model_id="mind_buffett", domain="价值", prototype_id="proto_4433")
        ]}
        gen = LLMStrategyGenerator(mock_llm_factory([payload]))
        result = gen.generate(1, prototype_dicts, mind_model_dicts, dim_matrix)
        assert len(result) == 1
        assert result[0].mind_model_id == "mind_buffett"


class TestGroundTruthValidation:
    def test_empty_prototypes_rejected(self, mock_llm_factory, mind_model_dicts, dim_matrix):
        gen = LLMStrategyGenerator(mock_llm_factory([{"strategies": []}]))
        with pytest.raises(ValueError):
            gen.generate(1, [], mind_model_dicts, dim_matrix)

    def test_dim_matrix_without_domains_rejected(
        self, mock_llm_factory, prototype_dicts, mind_model_dicts
    ):
        gen = LLMStrategyGenerator(mock_llm_factory([{"strategies": []}]))
        with pytest.raises(ValueError):
            gen.generate(1, prototype_dicts, mind_model_dicts, {"timing_logic": []})


class TestPromptAndContext:
    def test_prompt_includes_count(
        self, mock_llm_factory, prototype_dicts, mind_model_dicts, dim_matrix
    ):
        llm = mock_llm_factory([{"strategies": []}])
        gen = LLMStrategyGenerator(llm)
        gen.generate(7, prototype_dicts, mind_model_dicts, dim_matrix)
        assert llm.calls, "LLM 应被调用"
        prompt, context = llm.calls[0]
        assert "7" in prompt
        # context 应包含原型与大师的 ground truth
        assert "proto_" in context
        assert "mind_" in context
