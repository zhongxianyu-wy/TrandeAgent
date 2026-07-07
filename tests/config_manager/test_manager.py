"""T02/T09：ConfigManager 抽象接口 + DefaultConfigManager 测试。"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.config_manager.manager import ConfigManager, DefaultConfigManager
from src.config_manager.schema import ArenaSection

from tests.config_manager.conftest import (
    VALID_YAML,
    make_config,
    make_screener_rule,
)


class TestConfigManagerAbstract:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            ConfigManager()

    def test_has_all_abstract_methods(self):
        assert hasattr(ConfigManager, "load")
        assert hasattr(ConfigManager, "validate")
        assert hasattr(ConfigManager, "analyze_impact")
        assert hasattr(ConfigManager, "save_with_commit")
        assert hasattr(ConfigManager, "rollback")


class TestDefaultConfigManagerLoad:
    def test_load_from_path(self, tmp_path):
        p = tmp_path / "cfg.yaml"
        p.write_text(VALID_YAML, encoding="utf-8")
        mgr = DefaultConfigManager(p)
        cfg = mgr.load()
        assert cfg.observation_pool == ["000001", "000002"]

    def test_load_explicit_path(self, tmp_path):
        p1 = tmp_path / "a.yaml"
        p1.write_text(VALID_YAML, encoding="utf-8")
        mgr = DefaultConfigManager(tmp_path / "other.yaml")
        cfg = mgr.load(p1)
        assert cfg.observation_pool == ["000001", "000002"]


class TestDefaultConfigManagerValidate:
    def test_validate_ok(self):
        mgr = DefaultConfigManager(Path("dummy"))
        assert mgr.validate(VALID_YAML) == []

    def test_validate_finds_errors(self):
        mgr = DefaultConfigManager(Path("dummy"))
        bad = VALID_YAML.replace('op: ">="', 'op: "bad"')
        issues = mgr.validate(bad)
        assert len(issues) >= 1


class TestDefaultConfigManagerAnalyzeImpact:
    def test_analyze(self):
        mgr = DefaultConfigManager(Path("dummy"))
        old = make_config(pool=["001"])
        new = make_config(pool=["002"])
        impacts = mgr.analyze_impact(old, new)
        assert any(i.change_type == "pool" for i in impacts)


class TestSaveWithCommit:
    def test_save_in_git_repo(self, git_repo):
        cfg_path = git_repo / "strategies.yaml"
        mgr = DefaultConfigManager(cfg_path)
        cfg = make_config(pool=["001", "002"])
        commit_hash = mgr.save_with_commit(cfg, "add initial config")
        assert len(commit_hash) == 40
        # 文件已写入
        assert "001" in cfg_path.read_text(encoding="utf-8")
        # git 历史有记录
        entries = mgr.log()
        assert len(entries) == 1
        assert "add initial config" in entries[0]["message"]

    def test_save_multiple_commits(self, git_repo):
        cfg_path = git_repo / "strategies.yaml"
        mgr = DefaultConfigManager(cfg_path)
        mgr.save_with_commit(make_config(pool=["001"]), "first")
        mgr.save_with_commit(make_config(pool=["001", "002"]), "second")
        entries = mgr.log()
        assert len(entries) == 2

    def test_save_outside_repo(self, tmp_path):
        # tmp_path 不是 git 仓库
        cfg_path = tmp_path / "strategies.yaml"
        mgr = DefaultConfigManager(cfg_path)
        result = mgr.save_with_commit(make_config(), "test")
        assert result == ""
        # 文件仍写入
        assert cfg_path.exists()


class TestRollback:
    def test_rollback_and_reload(self, git_repo):
        cfg_path = git_repo / "strategies.yaml"
        mgr = DefaultConfigManager(cfg_path)
        mgr.save_with_commit(make_config(pool=["001", "002"]), "v1")
        h1 = mgr.log()[0]["hash"]
        mgr.save_with_commit(make_config(pool=["003", "004"]), "v2")

        # 回滚到 v1
        cfg = mgr.rollback(h1)
        assert cfg.observation_pool == ["001", "002"]

    def test_show_old_version(self, git_repo):
        cfg_path = git_repo / "strategies.yaml"
        mgr = DefaultConfigManager(cfg_path)
        mgr.save_with_commit(make_config(pool=["001"]), "v1")
        h1 = mgr.log()[0]["hash"]
        content = mgr.show(h1)
        assert "001" in content
