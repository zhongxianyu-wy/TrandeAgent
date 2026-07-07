"""T03：loader（YAML 加载 + ${VAR} 环境变量替换）测试。"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from src.config_manager.loader import (
    dump_config_yaml,
    find_env_var_refs,
    load_config,
    load_yaml,
    substitute_env_vars,
)

from tests.config_manager.conftest import VALID_YAML


class TestSubstituteEnvVars:
    def test_basic_substitution(self, monkeypatch):
        monkeypatch.setenv("MY_KEY", "secret123")
        result = substitute_env_vars("key: ${MY_KEY}")
        assert result == "key: secret123"

    def test_undefined_var_becomes_empty(self, monkeypatch):
        monkeypatch.delenv("UNDEFINED_VAR_XYZ", raising=False)
        result = substitute_env_vars("key: ${UNDEFINED_VAR_XYZ}")
        assert result == "key: "

    def test_multiple_vars(self, monkeypatch):
        monkeypatch.setenv("A", "1")
        monkeypatch.setenv("B", "2")
        result = substitute_env_vars("${A}-${B}")
        assert result == "1-2"

    def test_no_vars_unchanged(self):
        assert substitute_env_vars("plain text") == "plain text"

    def test_var_in_middle(self, monkeypatch):
        monkeypatch.setenv("HOST", "localhost")
        result = substitute_env_vars("http://${HOST}:8080")
        assert result == "http://localhost:8080"


class TestFindEnvVarRefs:
    def test_finds_all_unique(self):
        text = "${A} and ${B} and ${A}"
        assert find_env_var_refs(text) == ["A", "B"]

    def test_no_refs(self):
        assert find_env_var_refs("no vars") == []


class TestLoadYaml:
    def test_load_valid(self, tmp_path):
        p = tmp_path / "cfg.yaml"
        p.write_text(VALID_YAML, encoding="utf-8")
        data = load_yaml(p)
        assert data["observation_pool"] == ["000001", "000002"]
        assert len(data["screener_rules"]) == 1

    def test_load_empty_file(self, tmp_path):
        p = tmp_path / "empty.yaml"
        p.write_text("", encoding="utf-8")
        assert load_yaml(p) == {}

    def test_load_with_env_var(self, tmp_path, monkeypatch):
        monkeypatch.setenv("POOL_CODE", "999999")
        p = tmp_path / "cfg.yaml"
        p.write_text("observation_pool:\n  - ${POOL_CODE}\n", encoding="utf-8")
        data = load_yaml(p)
        # load_yaml 返回原始数据（YAML 把 999999 解析为 int），
        # 字符串强制转换在 AppConfig 校验层完成（load_config）
        assert data["observation_pool"] == [999999]


class TestLoadConfig:
    def test_load_valid_config(self, tmp_path):
        p = tmp_path / "cfg.yaml"
        p.write_text(VALID_YAML, encoding="utf-8")
        cfg = load_config(p)
        assert cfg.observation_pool == ["000001", "000002"]
        assert cfg.screener_rules[0].name == "r1"
        assert cfg.arena.strategy_count == 100


class TestDumpConfigYaml:
    def test_roundtrip(self, tmp_path):
        from tests.config_manager.conftest import make_config

        cfg = make_config()
        text = dump_config_yaml(cfg)
        # 写回文件再加载，验证 roundtrip
        p = tmp_path / "roundtrip.yaml"
        p.write_text(text, encoding="utf-8")
        cfg2 = load_config(p)
        assert cfg2.observation_pool == cfg.observation_pool
        assert len(cfg2.screener_rules) == len(cfg.screener_rules)

    def test_dump_is_valid_yaml(self):
        from tests.config_manager.conftest import make_config

        text = dump_config_yaml(make_config())
        data = yaml.safe_load(text)
        assert "observation_pool" in data
        assert "arena" in data
