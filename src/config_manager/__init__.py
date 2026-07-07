"""配置管理器（Feature #9 config-manager）。

集中管理用户策略规则（筛选 / 信号 / 竞技场），提供 YAML schema 校验、
配置变更影响范围检测、Git 版本管理。

技术约束（plan §1）：
- 不引入 gitpython —— git 操作用 subprocess。
- 不引入 deepdiff —— 配置 diff 用纯 Python 字典递归比较。
"""
from __future__ import annotations

from src.config_manager.example import build_example_config, generate_example
from src.config_manager.impact import analyze_impact
from src.config_manager.loader import (
    dump_config_yaml,
    find_env_var_refs,
    load_config,
    load_yaml,
    substitute_env_vars,
)
from src.config_manager.manager import ConfigManager, DefaultConfigManager, GitError
from src.config_manager.schema import AppConfig, ArenaSection, ChangeImpact
from src.config_manager.validator import ValidationIssue, validate_yaml
from src.config_manager.version import git_commit, git_log, git_rollback, git_show_file

__all__ = [
    # schema
    "AppConfig",
    "ArenaSection",
    "ChangeImpact",
    # manager
    "ConfigManager",
    "DefaultConfigManager",
    "GitError",
    # loader
    "load_config",
    "load_yaml",
    "dump_config_yaml",
    "substitute_env_vars",
    "find_env_var_refs",
    # validator
    "validate_yaml",
    "ValidationIssue",
    # impact
    "analyze_impact",
    # version
    "git_commit",
    "git_log",
    "git_rollback",
    "git_show_file",
    # example
    "generate_example",
    "build_example_config",
]
