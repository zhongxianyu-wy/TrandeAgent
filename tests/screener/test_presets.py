"""T10：预置规则集测试（4433 法则 / 聪明钱 + YAML 加载）。"""
from __future__ import annotations

import pytest

from src.screener.models import ScreenerConfig
from src.screener.presets import (
    PRESETS,
    get_preset,
    preset_4433,
    preset_quality,
)


class TestPreset4433:
    def test_returns_config(self):
        cfg = preset_4433()
        assert isinstance(cfg, ScreenerConfig)
        assert len(cfg.rules) >= 3

    def test_uses_percentile_top(self):
        cfg = preset_4433()
        ops = [r.op for r in cfg.rules]
        assert "percentile_top" in ops

    def test_has_weights(self):
        cfg = preset_4433()
        assert len(cfg.weights) > 0

    def test_rule_names_unique(self):
        cfg = preset_4433()
        names = [r.name for r in cfg.rules]
        assert len(names) == len(set(names))


class TestPresetQuality:
    def test_returns_config(self):
        cfg = preset_quality()
        assert isinstance(cfg, ScreenerConfig)
        assert len(cfg.rules) >= 2


class TestPresetsRegistry:
    def test_registry_contains_4433(self):
        assert "rule_4433" in PRESETS
        assert "quality" in PRESETS

    def test_registry_values_are_configs(self):
        for cfg in PRESETS.values():
            assert isinstance(cfg, ScreenerConfig)


class TestGetPreset:
    def test_get_from_yaml(self):
        # config/screener.yaml 存在 rule_4433
        cfg = get_preset("rule_4433")
        assert isinstance(cfg, ScreenerConfig)
        assert len(cfg.rules) >= 3

    def test_get_quality_from_yaml(self):
        cfg = get_preset("quality")
        assert isinstance(cfg, ScreenerConfig)

    def test_get_unknown_raises(self):
        with pytest.raises(KeyError):
            get_preset("does_not_exist")

    def test_fallback_to_programmatic(self, tmp_path):
        # 给一个不存在的 yaml 路径 → 回退程序化预设
        cfg = get_preset("rule_4433", config_path=tmp_path / "missing.yaml")
        assert isinstance(cfg, ScreenerConfig)

    def test_yaml_matches_programmatic(self):
        """YAML 预设与程序化预设一致。"""
        from_yaml = get_preset("rule_4433")
        prog = preset_4433()
        assert len(from_yaml.rules) == len(prog.rules)
        assert from_yaml.top_n == prog.top_n
