"""QwenClient —— 通义千问备选实现（T03）。

DashScope 提供 OpenAI 兼容模式，复用 DeepSeekClient 的协议逻辑，
仅切换 base_url / 默认模型。通过配置 provider=qwen 切换（ADR-002）。
"""
from __future__ import annotations

from src.analyzer.llm.deepseek_client import DeepSeekClient

# DashScope OpenAI 兼容端点
QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
QWEN_DEFAULT_MODEL = "qwen-plus"


class QwenClient(DeepSeekClient):
    """Qwen-Max/Plus 备选客户端（继承 DeepSeek 的 JSON mode 逻辑）。"""

    def __init__(
        self,
        api_key: str,
        base_url: str = QWEN_BASE_URL,
        model: str = QWEN_DEFAULT_MODEL,
        timeout: float = 60.0,
    ) -> None:
        super().__init__(api_key=api_key, base_url=base_url, model=model, timeout=timeout)
