"""T08：git 版本管理（subprocess）测试。

使用 tmp_path 初始化临时 git 仓库，不依赖主项目仓库。
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from src.config_manager.version import (
    GitError,
    git_commit,
    git_log,
    git_rollback,
    git_show_file,
    is_git_repo,
)


def _write_cfg(path: Path, pool: list[str]) -> Path:
    """写入一个简单的策略配置文件。"""
    lines = ["observation_pool:"]
    for code in pool:
        lines.append(f'  - "{code}"')
    lines.append("screener_rules: []")
    lines.append("signal_rules: []")
    lines.append("arena:")
    lines.append("  enabled: true")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


class TestGitCommit:
    def test_commit_returns_hash(self, git_repo):
        cfg = _write_cfg(git_repo / "strategies.yaml", ["001"])
        h = git_commit(cfg, "initial config")
        assert len(h) == 40  # full SHA-1

    def test_commit_no_changes_returns_head(self, git_repo):
        cfg = _write_cfg(git_repo / "strategies.yaml", ["001"])
        h1 = git_commit(cfg, "initial")
        # 再次提交相同内容
        h2 = git_commit(cfg, "no change")
        assert h1 == h2


class TestGitLog:
    def test_log_returns_entries(self, git_repo):
        cfg = _write_cfg(git_repo / "strategies.yaml", ["001"])
        git_commit(cfg, "first")
        _write_cfg(cfg, ["001", "002"])
        git_commit(cfg, "second")

        entries = git_log(cfg, n=10)
        assert len(entries) == 2
        assert "second" in entries[0]["message"]
        assert "first" in entries[1]["message"]
        assert len(entries[0]["hash"]) == 40

    def test_log_limit_n(self, git_repo):
        cfg = _write_cfg(git_repo / "strategies.yaml", ["001"])
        for i in range(5):
            _write_cfg(cfg, [f"00{i}"])
            git_commit(cfg, f"commit {i}")
        entries = git_log(cfg, n=3)
        assert len(entries) == 3


class TestGitShowFile:
    def test_show_old_version(self, git_repo):
        cfg = _write_cfg(git_repo / "strategies.yaml", ["001"])
        h1 = git_commit(cfg, "v1")
        _write_cfg(cfg, ["001", "002"])
        git_commit(cfg, "v2")

        old_content = git_show_file(cfg, h1)
        assert "001" in old_content
        assert "002" not in old_content


class TestGitRollback:
    def test_rollback_restores_file(self, git_repo):
        cfg = _write_cfg(git_repo / "strategies.yaml", ["001"])
        h1 = git_commit(cfg, "v1")
        _write_cfg(cfg, ["001", "002", "003"])
        git_commit(cfg, "v2")

        # 当前文件包含 003
        assert "003" in cfg.read_text(encoding="utf-8")

        git_rollback(cfg, h1)
        # 回滚后不含 003
        assert "003" not in cfg.read_text(encoding="utf-8")
        assert "001" in cfg.read_text(encoding="utf-8")


class TestIsGitRepo:
    def test_inside_repo(self, git_repo):
        cfg = git_repo / "strategies.yaml"
        cfg.write_text("observation_pool: []\n", encoding="utf-8")
        assert is_git_repo(cfg) is True

    def test_outside_repo(self, tmp_path):
        cfg = tmp_path / "strategies.yaml"
        cfg.write_text("observation_pool: []\n", encoding="utf-8")
        assert is_git_repo(cfg) is False


class TestGitError:
    def test_rollback_bad_commit_raises(self, git_repo):
        cfg = _write_cfg(git_repo / "strategies.yaml", ["001"])
        git_commit(cfg, "v1")
        with pytest.raises(GitError):
            git_rollback(cfg, "deadbeef" * 5)
