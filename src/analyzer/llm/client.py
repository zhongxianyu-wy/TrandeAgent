"""LLM 客户端抽象接口（T01）。

对应 ADR-002 / ADR-005。下游业务（FundAnalyzer）只依赖本抽象，
具体实现（DeepSeekClient / QwenClient）通过配置切换。
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class LLMClient(ABC):
    """LLM 客户端抽象。

    实现方需保证：
    - 以 metrics_json 为唯一事实来源，禁止编造指标
    - 返回结构化 dict（JSON mode），字段对齐 FundReport
    """

    @abstractmethod
    def analyze_fund(self, prompt: str, metrics_json: str) -> dict:
        """调用 LLM 生成基金分析报告。

        Args:
            prompt: 分析指令（含基金代码与格式约束）。
            metrics_json: 指标数据 JSON 字符串（唯一事实来源）。

        Returns:
            dict，结构对齐 FundReport（fund_code/one_liner/label/sections/
            recommendation_pool）。调用方负责后校验。
        """
