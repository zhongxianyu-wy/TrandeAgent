"""ConfigManager 抽象接口 + DefaultConfigManager 实现（T02/T09）。

对应 plan §3 接口契约。DefaultConfigManager 聚合 loader / validator / impact /
version 四个模块，提供端到端的配置管理能力。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from src.config_manager.impact import analyze_impact as _analyze_impact
from src.config_manager.loader import dump_config_yaml, load_config
from src.config_manager.schema import AppConfig, ChangeImpact
from src.config_manager.validator import ValidationIssue, validate_yaml
from src.config_manager.version import (
    GitError,
    git_commit,
    git_log,
    git_rollback,
    git_show_file,
    is_git_repo,
)


class ConfigManager(ABC):
    """配置管理器抽象接口（plan §3）。"""

    @abstractmethod
    def load(self, path: Path) -> AppConfig:
        """从 YAML 文件加载配置。"""

    @abstractmethod
    def validate(self, yaml_text: str) -> list[ValidationIssue]:
        """校验 YAML 文本，返回问题列表（空列表表示通过）。"""

    @abstractmethod
    def analyze_impact(
        self, old: AppConfig, new: AppConfig
    ) -> list[ChangeImpact]:
        """比较新旧配置，返回影响范围报告列表。"""

    @abstractmethod
    def save_with_commit(self, config: AppConfig, msg: str) -> None:
        """保存配置并自动 git commit。"""

    @abstractmethod
    def rollback(self, commit_hash: str) -> AppConfig:
        """回滚配置到指定 commit 并加载。"""


class DefaultConfigManager(ConfigManager):
    """默认实现：绑定一个 config_path 进行全部操作。"""

    def __init__(self, config_path: str | Path) -> None:
        self.config_path = Path(config_path)

    def load(self, path: str | Path | None = None) -> AppConfig:
        return load_config(path or self.config_path)

    def validate(self, yaml_text: str) -> list[ValidationIssue]:
        return validate_yaml(yaml_text)

    def analyze_impact(
        self, old: AppConfig, new: AppConfig
    ) -> list[ChangeImpact]:
        return _analyze_impact(old, new)

    def log(self, n: int = 10) -> list[dict]:
        """获取配置文件的 git 历史。"""
        return git_log(self.config_path, n)

    def save_with_commit(self, config: AppConfig, msg: str) -> str:
        """保存配置到 config_path 并 git commit，返回 commit hash。

        若 config_path 不在 git 仓库内，仅写文件不提交（返回空串）。
        """
        text = dump_config_yaml(config)
        self.config_path.write_text(text, encoding="utf-8")
        if is_git_repo(self.config_path):
            return git_commit(self.config_path, msg)
        return ""

    def rollback(self, commit_hash: str) -> AppConfig:
        """把 config_path 回滚到指定 commit 并重新加载。"""
        git_rollback(self.config_path, commit_hash)
        return self.load()

    def show(self, commit_hash: str) -> str:
        """读取指定 commit 下配置文件的原始内容。"""
        return git_show_file(self.config_path, commit_hash)


__all__ = [
    "ConfigManager",
    "DefaultConfigManager",
    "GitError",
]
