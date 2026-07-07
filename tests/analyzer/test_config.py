"""T14: 配置加载测试。"""
from __future__ import annotations

import pytest

from src.analyzer.config import (
    AnalyzerConfig,
    LLMConfig,
    build_llm_client,
    load_analyzer_config,
)
from src.analyzer.llm import DeepSeekClient, QwenClient


class TestLoadConfig:
    def test_defaults_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        cfg = load_analyzer_config(tmp_path / "missing.yaml")
        assert isinstance(cfg, AnalyzerConfig)
        assert cfg.llm.provider == "deepseek"
        assert cfg.years == 5
        assert cfg.max_retries == 1

    def test_load_yaml(self, tmp_path):
        path = tmp_path / "analyzer.yaml"
        path.write_text(
            "funds: ['000001', '161725']\n"
            "years: 3\n"
            "max_retries: 2\n"
            "llm:\n"
            "  provider: qwen\n"
            "  model: qwen-max\n"
            "  base_url: 'https://example.com/v1'\n",
            encoding="utf-8",
        )
        cfg = load_analyzer_config(path)
        assert cfg.funds == ["000001", "161725"]
        assert cfg.years == 3
        assert cfg.max_retries == 2
        assert cfg.llm.provider == "qwen"
        assert cfg.llm.model == "qwen-max"

    def test_env_placeholder_expansion(self, tmp_path):
        path = tmp_path / "analyzer.yaml"
        path.write_text("llm:\n  api_key: ${TEST_KEY}\n", encoding="utf-8")
        cfg = load_analyzer_config(path, env={"TEST_KEY": "sk-from-env"})
        assert cfg.llm.api_key == "sk-from-env"

    def test_api_key_resolved_by_provider_env(self, tmp_path):
        """无显式 api_key 时按 provider 从环境变量取。"""
        path = tmp_path / "analyzer.yaml"
        path.write_text("llm:\n  provider: deepseek\n", encoding="utf-8")
        cfg = load_analyzer_config(path, env={"DEEPSEEK_API_KEY": "sk-deep"})
        assert cfg.llm.api_key == "sk-deep"

    def test_qwen_api_key_env(self, tmp_path):
        path = tmp_path / "analyzer.yaml"
        path.write_text("llm:\n  provider: qwen\n", encoding="utf-8")
        cfg = load_analyzer_config(path, env={"DASHSCOPE_API_KEY": "sk-dash"})
        assert cfg.llm.api_key == "sk-dash"

    def test_explicit_key_wins(self, tmp_path):
        path = tmp_path / "analyzer.yaml"
        path.write_text("llm:\n  api_key: explicit\n", encoding="utf-8")
        cfg = load_analyzer_config(path, env={"DEEPSEEK_API_KEY": "ignored"})
        assert cfg.llm.api_key == "explicit"


class TestBuildLLMClient:
    def test_deepseek(self):
        cfg = AnalyzerConfig(llm=LLMConfig(provider="deepseek", api_key="k"))
        client = build_llm_client(cfg)
        assert isinstance(client, DeepSeekClient)

    def test_qwen(self):
        cfg = AnalyzerConfig(llm=LLMConfig(provider="qwen", api_key="k"))
        client = build_llm_client(cfg)
        assert isinstance(client, QwenClient)

    def test_override_llm_config(self):
        cfg = AnalyzerConfig(llm=LLMConfig(provider="deepseek", api_key="k"))
        override = LLMConfig(provider="qwen", api_key="k2")
        client = build_llm_client(cfg, llm_config=override)
        assert isinstance(client, QwenClient)
