"""T01：Pydantic 规则模型 + YAML 加载测试。"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.screener.models import (
    Rule,
    ScreenResult,
    ScreenerConfig,
    load_yaml_config,
    load_yaml_presets,
)


class TestRule:
    def test_basic_rule(self):
        r = Rule(name="r1", field="l2_performance.sharpe", op=">=", value=1.0)
        assert r.name == "r1"
        assert r.field == "l2_performance.sharpe"
        assert r.op == ">="
        assert r.value == 1.0

    def test_between_value_list(self):
        r = Rule(name="scale", field="scale", op="between", value=[2.0, 50.0])
        assert r.value == [2.0, 50.0]

    def test_in_value_list(self):
        r = Rule(name="style", field="style_box", op="in", value=["大盘成长", "中盘成长"])
        assert r.value == ["大盘成长", "中盘成长"]

    def test_invalid_operator_rejected(self):
        with pytest.raises(Exception):
            Rule(name="r", field="sharpe", op="!=", value=1.0)


class TestScreenerConfig:
    def test_defaults(self):
        cfg = ScreenerConfig(rules=[Rule(name="r", field="sharpe", op=">=", value=1.0)])
        assert cfg.weights == {}
        assert cfg.top_n == 20

    def test_weight_of_default(self):
        cfg = ScreenerConfig(rules=[Rule(name="r", field="sharpe", op=">=", value=1.0)])
        assert cfg.weight_of("r") == 1.0
        assert cfg.weight_of("missing") == 1.0

    def test_weight_of_explicit(self):
        cfg = ScreenerConfig(
            rules=[Rule(name="r", field="sharpe", op=">=", value=1.0)],
            weights={"r": 2.5},
        )
        assert cfg.weight_of("r") == 2.5

    def test_top_n_must_be_positive(self):
        with pytest.raises(Exception):
            ScreenerConfig(
                rules=[Rule(name="r", field="sharpe", op=">=", value=1.0)],
                top_n=0,
            )


class TestScreenResult:
    def test_model(self):
        res = ScreenResult(fund_code="F001", score=3.5, matched_rules=["a", "b"])
        assert res.fund_code == "F001"
        assert res.score == 3.5
        assert res.matched_rules == ["a", "b"]


class TestYamlLoading:
    def test_load_yaml_config(self):
        path = Path("config/screener.yaml")
        cfg = load_yaml_config(path)
        assert len(cfg.rules) >= 1
        assert cfg.top_n >= 1
        assert all(isinstance(r, Rule) for r in cfg.rules)

    def test_load_yaml_presets(self):
        path = Path("config/screener.yaml")
        presets = load_yaml_presets(path)
        assert "rule_4433" in presets
        assert "quality" in presets
        assert len(presets["rule_4433"].rules) >= 3

    def test_load_yaml_presets_missing_file(self, tmp_path):
        # 空文件 → 空预设字典
        p = tmp_path / "empty.yaml"
        p.write_text("", encoding="utf-8")
        assert load_yaml_presets(p) == {}
