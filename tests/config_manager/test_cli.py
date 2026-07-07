"""T10：CLI 入口测试。"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.config_manager.__main__ import main

from tests.config_manager.conftest import VALID_YAML


class TestCliValidate:
    def test_validate_ok(self, tmp_path, capsys):
        p = tmp_path / "cfg.yaml"
        p.write_text(VALID_YAML, encoding="utf-8")
        rc = main(["validate", str(p)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "校验通过" in out

    def test_validate_fail(self, tmp_path, capsys):
        p = tmp_path / "cfg.yaml"
        p.write_text(VALID_YAML.replace('op: ">="', 'op: "bad"'), encoding="utf-8")
        rc = main(["validate", str(p)])
        assert rc == 1
        out = capsys.readouterr().out
        assert "问题" in out


class TestCliImpact:
    def test_impact_no_change(self, tmp_path, capsys):
        p = tmp_path / "cfg.yaml"
        p.write_text(VALID_YAML, encoding="utf-8")
        rc = main(["impact", str(p), str(p)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "无配置变更" in out

    def test_impact_with_change(self, tmp_path, capsys):
        old = tmp_path / "old.yaml"
        new = tmp_path / "new.yaml"
        old.write_text(VALID_YAML, encoding="utf-8")
        new_yaml = VALID_YAML.replace("- \"000002\"", "- \"000099\"")
        new.write_text(new_yaml, encoding="utf-8")
        rc = main(["impact", str(old), str(new)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "pool" in out


class TestCliLog:
    def test_log_no_repo(self, tmp_path, capsys):
        p = tmp_path / "cfg.yaml"
        p.write_text(VALID_YAML, encoding="utf-8")
        rc = main(["log", str(p)])
        # tmp_path 非 git 仓库 -> GitError
        assert rc == 1

    def test_log_with_repo(self, git_repo, capsys):
        from src.config_manager.manager import DefaultConfigManager
        from tests.config_manager.conftest import make_config

        p = git_repo / "cfg.yaml"
        mgr = DefaultConfigManager(p)
        mgr.save_with_commit(make_config(pool=["001"]), "test commit")
        rc = main(["log", str(p)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "test commit" in out


class TestCliRollback:
    def test_rollback(self, git_repo, capsys):
        from src.config_manager.manager import DefaultConfigManager
        from tests.config_manager.conftest import make_config

        p = git_repo / "cfg.yaml"
        mgr = DefaultConfigManager(p)
        mgr.save_with_commit(make_config(pool=["001"]), "v1")
        h = mgr.log()[0]["hash"]
        mgr.save_with_commit(make_config(pool=["002"]), "v2")

        rc = main(["rollback", str(p), h])
        assert rc == 0
        out = capsys.readouterr().out
        assert "回滚" in out

    def test_rollback_bad_commit(self, git_repo, capsys):
        from src.config_manager.manager import DefaultConfigManager
        from tests.config_manager.conftest import make_config

        p = git_repo / "cfg.yaml"
        mgr = DefaultConfigManager(p)
        mgr.save_with_commit(make_config(), "v1")
        rc = main(["rollback", str(p), "badhash"])
        assert rc == 1


class TestCliExample:
    def test_example_to_stdout(self, capsys):
        rc = main(["example"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "observation_pool" in out
        assert "screener_rules" in out

    def test_example_to_file(self, tmp_path, capsys):
        out_file = tmp_path / "example.yaml"
        rc = main(["example", "--out", str(out_file)])
        assert rc == 0
        assert out_file.exists()
        content = out_file.read_text(encoding="utf-8")
        assert "observation_pool" in content
