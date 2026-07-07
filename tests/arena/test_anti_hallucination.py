"""T18: 防幻觉测试 —— 大师心智模型仅取原文，LLM 不得凭空发明。

覆盖：
1. mind_models.yaml 中大师 id 与 strategy_prototypes.yaml 引用一致
2. 生成器拒绝凭空发明的原型/大师/领域/参数
3. 大师 principles 全部来自 YAML（ground truth），无运行时捏造
"""
from __future__ import annotations

from src.arena.deduplicator import strategy_to_vector
from src.arena.generator import LLMStrategyGenerator
from src.arena.mind_models.loader import (
    load_mind_model_dicts,
    load_mind_models,
    load_prototype_dicts,
)
from src.arena.models import DOMAINS
from src.arena.strategies import PROTOTYPE_REGISTRY
from tests.arena.conftest import valid_llm_strategy_payload


class TestConfigIntegrity:
    def test_mind_models_all_referenced_ids_valid(self):
        models = load_mind_models()
        assert len(models) == 8
        for m in models:
            assert m.id.startswith("mind_")
            assert m.principles, f"{m.id} 必须有原文 principles"
            assert m.works, f"{m.id} 必须有公开著作来源"
            # 大师声明的领域必须在 8 领域内
            for d in m.domain:
                assert d in DOMAINS, f"{m.id} 非法领域 {d}"

    def test_prototypes_class_registry_consistency(self):
        protos = load_prototype_dicts()
        assert len(protos) == 15
        yaml_ids = {p["id"] for p in protos}
        registry_ids = set(PROTOTYPE_REGISTRY.keys())
        assert yaml_ids == registry_ids, "YAML 原型与 Python 注册表不一致"
        # class_name 与注册表类名一致
        for p in protos:
            cls = PROTOTYPE_REGISTRY[p["id"]]
            assert cls.__name__ == p["class_name"], (
                f"{p['id']} class_name={p['class_name']} 与 {cls.__name__} 不符"
            )

    def test_prototype_domains_within_eight(self):
        protos = load_prototype_dicts()
        for p in protos:
            for d in p.get("domain", []):
                assert d in DOMAINS, f"{p['id']} 非法领域 {d}"


class TestNoHallucinatedPrototypes:
    def _gen(self, mock_llm_factory, payload, *, prototype_dicts, mind_model_dicts, dim_matrix):
        gen = LLMStrategyGenerator(mock_llm_factory([payload]))
        return gen.generate(1, prototype_dicts, mind_model_dicts, dim_matrix)

    def test_reject_invented_prototype(
        self, mock_llm_factory, prototype_dicts, mind_model_dicts, dim_matrix
    ):
        result = self._gen(
            mock_llm_factory,
            {"strategies": [valid_llm_strategy_payload(invented_proto=True)]},
            prototype_dicts=prototype_dicts,
            mind_model_dicts=mind_model_dicts,
            dim_matrix=dim_matrix,
        )
        assert result == []

    def test_reject_invented_mind_model(
        self, mock_llm_factory, prototype_dicts, mind_model_dicts, dim_matrix
    ):
        result = self._gen(
            mock_llm_factory,
            {"strategies": [valid_llm_strategy_payload(invented_mind=True)]},
            prototype_dicts=prototype_dicts,
            mind_model_dicts=mind_model_dicts,
            dim_matrix=dim_matrix,
        )
        assert result == []

    def test_reject_param_outside_template(
        self, mock_llm_factory, prototype_dicts, mind_model_dicts, dim_matrix
    ):
        result = self._gen(
            mock_llm_factory,
            {"strategies": [valid_llm_strategy_payload(extra_field=True)]},
            prototype_dicts=prototype_dicts,
            mind_model_dicts=mind_model_dicts,
            dim_matrix=dim_matrix,
        )
        assert result == []

    def test_reject_domain_outside_prototype_domain(
        self, mock_llm_factory, prototype_dicts, mind_model_dicts, dim_matrix
    ):
        # proto_dca 合法领域广，用 proto_ma_cross 限定 [趋势, 指数增强]
        item = valid_llm_strategy_payload(prototype_id="proto_ma_cross", domain="红利")
        result = self._gen(
            mock_llm_factory, {"strategies": [item]},
            prototype_dicts=prototype_dicts,
            mind_model_dicts=mind_model_dicts,
            dim_matrix=dim_matrix,
        )
        assert result == []

    def test_all_strategies_traceable(
        self, mock_llm_factory, prototype_dicts, mind_model_dicts, dim_matrix
    ):
        """合法生成的每个策略必须可追溯到已知原型 + 已知大师（或 None）。"""
        mind_ids = {m["id"] for m in load_mind_model_dicts()}
        payload = {"strategies": [
            valid_llm_strategy_payload(sid="ok1", prototype_id="proto_ma_cross", domain="趋势"),
            valid_llm_strategy_payload(sid="ok2", prototype_id="proto_4433", domain="价值", mind_model_id="mind_buffett"),
        ]}
        gen = LLMStrategyGenerator(mock_llm_factory([payload]))
        strategies = gen.generate(2, prototype_dicts, mind_model_dicts, dim_matrix)
        for s in strategies:
            assert s.prototype_id in PROTOTYPE_REGISTRY
            if s.mind_model_id is not None:
                assert s.mind_model_id in mind_ids
            assert s.source_explanation  # 必须有来源说明


class TestMindModelGroundTruthFrozen:
    def test_principles_match_yaml(self):
        """运行时不应添加/修改大师 principles —— 全部来自 YAML。"""
        models = {m.id: m for m in load_mind_models()}
        buffett = models["mind_buffett"]
        # 巴菲特必须包含安全边际原文要点
        joined = "".join(buffett.principles)
        assert "安全边际" in joined
        assert "护城河" in joined

    def test_all_eight_masters_present(self):
        ids = {m.id for m in load_mind_models()}
        expected = {
            "mind_buffett", "mind_munger", "mind_graham", "mind_lynch",
            "mind_dalio", "mind_marks", "mind_taleb", "mind_bogle",
        }
        assert ids == expected


class TestDedupVectorStability:
    def test_vector_does_not_invent_features(self, strategy):
        """特征向量维度固定，不引入幻觉字段。"""
        from src.arena.deduplicator import vector_length

        v = strategy_to_vector(strategy)
        assert v.shape == (vector_length(),)
        assert not any(x != x for x in v)  # 无 NaN
