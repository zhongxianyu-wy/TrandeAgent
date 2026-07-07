"""DeepSeekClient —— OpenAI 兼容协议调 DeepSeek-V3（T02）。

对应 ADR-002。使用 openai SDK（已安装 >=1.0），强制 JSON mode 输出（防幻觉第二层）。
"""
from __future__ import annotations

import json
import re

from loguru import logger

from src.analyzer.llm.client import LLMClient
from src.analyzer.llm.prompts import SYSTEM_PROMPT

# 代码围栏剥离（部分模型即便要求纯 JSON 仍会包 ```json ... ```）
_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def _strip_code_fence(text: str) -> str:
    return _FENCE_PATTERN.sub("", text.strip()).strip()


def _parse_json_content(content: str) -> dict:
    """解析 LLM 返回内容为 dict，兼容代码围栏。"""
    cleaned = _strip_code_fence(content)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM 返回非法 JSON：{e}") from e


class DeepSeekClient(LLMClient):
    """DeepSeek（OpenAI 兼容协议）客户端。"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
        timeout: float = 60.0,
    ) -> None:
        # 延迟导入，便于测试在无 openai 环境下 mock
        from openai import OpenAI

        if not api_key:
            raise ValueError("DeepSeek api_key 不能为空")
        self._model = model
        self._timeout = timeout
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    def analyze_fund(self, prompt: str, metrics_json: str) -> dict:
        """调用 DeepSeek 生成报告（JSON mode）。"""
        user_content = f"指标数据（唯一事实来源）：\n{metrics_json}\n\n{prompt}"
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            timeout=self._timeout,
        )
        content = resp.choices[0].message.content or ""
        if getattr(resp, "usage", None):
            logger.debug(
                "DeepSeek token 用量：input={} output={}",
                resp.usage.prompt_tokens,
                resp.usage.completion_tokens,
            )
        return _parse_json_content(content)
