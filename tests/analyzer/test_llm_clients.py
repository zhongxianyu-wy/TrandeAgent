"""T02/T03: DeepSeek / Qwen 客户端测试（mock openai，不调真实 API）。"""
from __future__ import annotations

import json

import pytest

from src.analyzer.llm.deepseek_client import DeepSeekClient, _parse_json_content
from src.analyzer.llm.qwen_client import QWEN_BASE_URL, QWEN_DEFAULT_MODEL, QwenClient


# ---------- fake openai 响应链 ----------


class _Msg:
    def __init__(self, content: str) -> None:
        self.content = content


class _Choice:
    def __init__(self, content: str) -> None:
        self.message = _Msg(content)


class _Usage:
    prompt_tokens = 100
    completion_tokens = 50


class _Resp:
    def __init__(self, content: str) -> None:
        self.choices = [_Choice(content)]
        self.usage = _Usage()


class _Completions:
    def __init__(self, return_contents: list[str]) -> None:
        self._contents = list(return_contents)
        self.last_kwargs: dict | None = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        content = self._contents.pop(0) if self._contents else "{}"
        return _Resp(content)


class _Chat:
    def __init__(self, contents: list[str]) -> None:
        self.completions = _Completions(contents)


class _FakeOpenAI:
    def __init__(self, contents: list[str]) -> None:
        self.chat = _Chat(contents)


# ---------- DeepSeek ----------


class TestDeepSeekClient:
    def test_requires_api_key(self):
        with pytest.raises(ValueError):
            DeepSeekClient(api_key="")

    def test_parses_json(self):
        client = DeepSeekClient(api_key="sk-test")
        client._client = _FakeOpenAI(['{"fund_code":"000001","label":"建议"}'])
        result = client.analyze_fund("prompt", "{}")
        assert result["fund_code"] == "000001"
        assert result["label"] == "建议"

    def test_strips_code_fence(self):
        """模型即便包 ```json 也应正确解析。"""
        client = DeepSeekClient(api_key="sk-test")
        fenced = '```json\n{"fund_code":"000001"}\n```'
        client._client = _FakeOpenAI([fenced])
        result = client.analyze_fund("p", "{}")
        assert result["fund_code"] == "000001"

    def test_messages_structure(self):
        """校验 system/user 消息组装 + metrics 注入。"""
        client = DeepSeekClient(api_key="sk-test")
        fake = _FakeOpenAI(["{}"])
        client._client = fake
        client.analyze_fund("分析指令XYZ", "指标JSON_ABC")
        kwargs = fake.chat.completions.last_kwargs
        assert kwargs is not None
        messages = kwargs["messages"]
        assert messages[0]["role"] == "system"
        assert "【依据：指标名=数值】" in messages[0]["content"]  # 强约束 system prompt
        assert messages[1]["role"] == "user"
        assert "指标JSON_ABC" in messages[1]["content"]
        assert "分析指令XYZ" in messages[1]["content"]
        assert kwargs["response_format"] == {"type": "json_object"}

    def test_invalid_json_raises(self):
        client = DeepSeekClient(api_key="sk-test")
        client._client = _FakeOpenAI(["not a json"])
        with pytest.raises(ValueError):
            client.analyze_fund("p", "{}")

    def test_empty_content_raises(self):
        client = DeepSeekClient(api_key="sk-test")
        client._client = _FakeOpenAI([""])
        with pytest.raises(ValueError):
            client.analyze_fund("p", "{}")

    def test_model_propagated(self):
        client = DeepSeekClient(api_key="sk-test", model="deepseek-reasoner")
        client._client = _FakeOpenAI(["{}"])
        client.analyze_fund("p", "{}")
        assert client._client.chat.completions.last_kwargs["model"] == "deepseek-reasoner"


# ---------- parse helper ----------


class TestParseJsonContent:
    def test_plain(self):
        assert _parse_json_content('{"a":1}') == {"a": 1}

    def test_fence(self):
        assert _parse_json_content('```json\n{"a":1}\n```') == {"a": 1}

    def test_invalid(self):
        with pytest.raises(ValueError):
            _parse_json_content("nope")


# ---------- Qwen ----------


class TestQwenClient:
    def test_default_base_url_and_model(self):
        c = QwenClient(api_key="sk-test")
        assert c._model == QWEN_DEFAULT_MODEL
        # 底层 OpenAI 客户端 base_url 已设置
        assert QWEN_BASE_URL in str(c._client.base_url)

    def test_inherits_json_mode(self):
        c = QwenClient(api_key="sk-test")
        c._client = _FakeOpenAI(['{"fund_code":"000001","label":"回避"}'])
        result = c.analyze_fund("p", "{}")
        assert result["label"] == "回避"

    def test_custom_model(self):
        c = QwenClient(api_key="sk-test", model="qwen-max")
        assert c._model == "qwen-max"
