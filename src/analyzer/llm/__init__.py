"""LLM 客户端层（Feature #6 防幻觉核心）。

抽象 LLMClient + DeepSeek/Qwen 实现 + 强约束 prompt 模板。
"""
from src.analyzer.llm.client import LLMClient
from src.analyzer.llm.deepseek_client import DeepSeekClient
from src.analyzer.llm.prompts import (
    REPORT_SECTIONS,
    SYSTEM_PROMPT,
    build_user_prompt,
    estimate_tokens,
)
from src.analyzer.llm.qwen_client import QWEN_BASE_URL, QWEN_DEFAULT_MODEL, QwenClient

__all__ = [
    "LLMClient",
    "DeepSeekClient",
    "QwenClient",
    "QWEN_BASE_URL",
    "QWEN_DEFAULT_MODEL",
    "SYSTEM_PROMPT",
    "REPORT_SECTIONS",
    "build_user_prompt",
    "estimate_tokens",
]
