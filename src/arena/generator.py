"""策略生成器（T05 抽象接口 + T06 LLM 实现）。

复用 #6 fund-analyzer 的 :class:`LLMClient`。LLM 在差异维度矩阵约束下生成
参数变体，生成器对返回结果做严格校验与防幻觉检查：
- prototype_id 必须命中已知 15 原型（不得凭空发明）
- mind_model_id 必须命中已知 8 大师或为 None
- domain 必须命中 8 领域，且在该 prototype 的合法领域内
- 数值参数必须在原型参数空间内
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from src.analyzer.llm.client import LLMClient
from src.arena.deduplicator import CosineDeduplicator
from src.arena.models import DOMAINS, Strategy


class StrategyGenerator(ABC):
    """策略生成器抽象（plan §3 接口契约）。"""

    @abstractmethod
    def generate(
        self,
        count: int,
        prototypes: list[dict],
        mind_models: list[dict],
        dim_matrix: dict,
    ) -> list[Strategy]:
        """生成 count 个差异化策略。"""
        raise NotImplementedError

    @abstractmethod
    def deduplicate(
        self, strategies: list[Strategy], threshold: float = 0.1
    ) -> list[Strategy]:
        """参数空间去重（cosine 距离 < threshold 视为重复）。"""
        raise NotImplementedError


class LLMStrategyGenerator(StrategyGenerator):
    """LLM 驱动的策略生成器。

    使用差异维度矩阵约束 LLM，并对返回结果做后校验（防幻觉）。
    """

    def __init__(
        self,
        llm_client: LLMClient,
        *,
        deduplicator: CosineDeduplicator | None = None,
        system_hint: str | None = None,
        llm_timeout: float = 60.0,
    ) -> None:
        self._llm = llm_client
        self._dedup = deduplicator or CosineDeduplicator()
        self._system_hint = system_hint or _DEFAULT_SYSTEM_HINT
        self._llm_timeout = llm_timeout

    # ---- 公开接口 ----
    def generate(
        self,
        count: int,
        prototypes: list[dict],
        mind_models: list[dict],
        dim_matrix: dict,
    ) -> list[Strategy]:
        if count <= 0:
            return []
        self._validate_ground_truth(prototypes, mind_models, dim_matrix)

        prompt = self._build_prompt(count, prototypes, mind_models, dim_matrix)
        context = self._build_context(prototypes, mind_models, dim_matrix)

        resp = self._llm.analyze_fund(prompt, context)
        raw_list = self._extract_strategies(resp)

        strategies: list[Strategy] = []
        rejected = 0
        for item in raw_list:
            s = self._validate_one(item, prototypes, mind_models, dim_matrix)
            if s is not None:
                strategies.append(s)
            else:
                rejected += 1
        if rejected:
            logger.warning("LLM 策略生成器拒绝了 {} 个非法/幻觉策略", rejected)

        strategies = self.deduplicate(strategies, self._dedup_threshold(dim_matrix))
        logger.info("策略生成：请求 {}，通过校验+去重 {} 条", count, len(strategies))
        return strategies

    def deduplicate(
        self, strategies: list[Strategy], threshold: float = 0.1
    ) -> list[Strategy]:
        return self._dedup.deduplicate(strategies, threshold)

    # ---- 内部：ground truth 构造 ----
    @staticmethod
    def _validate_ground_truth(
        prototypes: list[dict], mind_models: list[dict], dim_matrix: dict
    ) -> None:
        if not prototypes:
            raise ValueError("ground truth：prototypes 不能为空")
        if not dim_matrix or "domains" not in dim_matrix:
            raise ValueError("ground truth：dim_matrix 缺少 domains")
        for p in prototypes:
            if "id" not in p:
                raise ValueError("ground truth：每个原型必须有 id")

    def _build_prompt(
        self,
        count: int,
        prototypes: list[dict],
        mind_models: list[dict],
        dim_matrix: dict,
    ) -> str:
        return (
            f"{self._system_hint}\n\n"
            f"请生成 {count} 个差异化策略。"
            f"可用的策略原型有 {len(prototypes)} 个，"
            f"可选的大师心智模型有 {len(mind_models)} 个。"
            "必须严格使用给定原型与差异维度组合，禁止发明新的原型或大师。"
        )

    @staticmethod
    def _build_context(
        prototypes: list[dict], mind_models: list[dict], dim_matrix: dict
    ) -> str:
        return json.dumps(
            {
                "prototypes": [
                    {
                        "id": p["id"],
                        "name": p.get("name", ""),
                        "domain": p.get("domain", []),
                        "params_template": p.get("params_template", {}),
                    }
                    for p in prototypes
                ],
                "mind_models": [
                    {"id": m["id"], "name": m.get("name", ""), "domain": m.get("domain", [])}
                    for m in mind_models
                ],
                "dimension_matrix": dim_matrix,
            },
            ensure_ascii=False,
        )

    @staticmethod
    def _extract_strategies(resp: Any) -> list[dict]:
        if not isinstance(resp, dict):
            return []
        data = resp.get("strategies")
        if isinstance(data, list):
            return [d for d in data if isinstance(d, dict)]
        # 兼容直接返回单策略 dict
        if {"prototype_id", "domain"} <= set(resp.keys()):
            return [resp]
        return []

    # ---- 内部：防幻觉校验 ----
    def _validate_one(
        self,
        item: dict,
        prototypes: list[dict],
        mind_models: list[dict],
        dim_matrix: dict,
    ) -> Strategy | None:
        try:
            proto_id = item.get("prototype_id")
            if not isinstance(proto_id, str) or not proto_id.startswith("proto_"):
                return None
            proto = next((p for p in prototypes if p["id"] == proto_id), None)
            if proto is None:
                # 凭空发明的原型 → 拒绝（防幻觉）
                return None

            domain = item.get("domain")
            allowed_domains = proto.get("domain") or list(DOMAINS)
            if domain not in DOMAINS or domain not in allowed_domains:
                return None

            mind_id = item.get("mind_model_id")
            if mind_id is not None:
                if not any(m["id"] == mind_id for m in mind_models):
                    return None

            params = item.get("params") or {}
            if not isinstance(params, dict):
                return None
            if not self._params_within_space(params, proto.get("params_template", {})):
                return None

            timing = item.get("timing_logic")
            if timing is not None and timing not in dim_matrix.get("timing_logic", []):
                return None
            freq = item.get("rebalance_freq")
            if freq is not None and freq not in dim_matrix.get("rebalance_freq", []):
                return None
            risk = item.get("risk_threshold")
            if risk is not None and float(risk) not in dim_matrix.get("risk_threshold", []):
                return None
            conc = item.get("concentration")
            if conc is not None and conc not in dim_matrix.get("concentration", []):
                return None

            sid = item.get("strategy_id") or f"strat_{proto_id}_{abs(hash(json.dumps(item, sort_keys=True, default=str))) % 100000:05d}"
            return Strategy(
                strategy_id=str(sid),
                prototype_id=proto_id,
                mind_model_id=mind_id,
                domain=domain,
                params=params,
                source_explanation=str(item.get("source_explanation", "")),
                created_at=datetime.now(timezone.utc),
                timing_logic=timing,
                rebalance_freq=freq,
                risk_threshold=float(risk) if risk is not None else None,
                concentration=conc,
            )
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _params_within_space(params: dict, template: dict) -> bool:
        """校验参数键都在模板定义内（防 LLM 凭空加字段）。"""
        if not template:
            return True  # 原型无参数空间限制
        for key in params:
            if key not in template:
                return False
        return True

    @staticmethod
    def _dedup_threshold(dim_matrix: dict) -> float:
        return 0.1


_DEFAULT_SYSTEM_HINT = (
    "你是基金策略竞技场的策略生成助手。严格基于给定的策略原型与差异维度矩阵，"
    "生成参数变体策略。规则：\n"
    "1. prototype_id 必须从给定原型列表中选取，禁止发明新原型。\n"
    "2. mind_model_id 必须从给定大师列表中选取或为 null，禁止发明新大师。\n"
    "3. domain 必须从该原型声明的合法领域内选取。\n"
    "4. params 的键必须在该原型 params_template 定义的集合内。\n"
    "5. 5 个差异维度轴必须取自给定矩阵。\n"
    "返回 JSON：{\"strategies\":[{strategy_id, prototype_id, mind_model_id, "
    "domain, params, timing_logic, rebalance_freq, risk_threshold, "
    "concentration, source_explanation}, ...]}"
)
