"""T11：示例配置生成测试。"""
from __future__ import annotations

import yaml
from pathlib import Path

import pytest

from src.config_manager.example import build_example_config, generate_example, write_example
from src.config_manager.loader import load_config
from src.config_manager.schema import AppConfig


class TestBuildExampleConfig:
    def test_returns_valid_config(self):
        cfg = build_example_config()
        assert isinstance(cfg, AppConfig)
        assert len(cfg.observation_pool) > 0
        assert len(cfg.screener_rules) > 0
        assert len(cfg.signal_rules) > 0
        assert cfg.arena.strategy_count > 0


class TestGenerateExample:
    def test_has_header_comment(self):
        text = generate_example()
        assert text.startswith("#")

    def test_is_loadable(self, tmp_path):
        text = generate_example()
        # 去掉注释行后可被 safe_load 解析
        p = tmp_path / "example.yaml"
        p.write_text(text, encoding="utf-8")
        cfg = load_config(p)
        assert len(cfg.observation_pool) >= 1
        assert len(cfg.screener_rules) >= 1


class TestWriteExample:
    def test_writes_file(self, tmp_path):
        p = tmp_path / "out.yaml"
        result = write_example(p)
        assert result == p
        assert p.exists()
        content = p.read_text(encoding="utf-8")
        assert "observation_pool" in content
