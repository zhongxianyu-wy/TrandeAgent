"""YAML 加载 + ${VAR} 环境变量替换（T03）。

支持 ``${VAR}`` 引用环境变量（如 LLM API Key）。未定义的环境变量替换为空字符串。
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import yaml

from src.config_manager.schema import AppConfig

_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def substitute_env_vars(text: str) -> str:
    """把 ``${VAR}`` 替换为环境变量值，未定义则替换为空字符串。"""
    return _VAR_PATTERN.sub(
        lambda m: os.environ.get(m.group(1), ""), text
    )


def find_env_var_refs(text: str) -> list[str]:
    """返回文本中引用的所有环境变量名（去重，保持顺序）。"""
    seen: set[str] = set()
    names: list[str] = []
    for m in _VAR_PATTERN.finditer(text):
        name = m.group(1)
        if name not in seen:
            seen.add(name)
            names.append(name)
    return names


def load_yaml(path: str | Path) -> dict:
    """读取 YAML 文件并做 ``${VAR}`` 替换，返回原始 dict（未校验）。"""
    raw = Path(path).read_text(encoding="utf-8")
    substituted = substitute_env_vars(raw)
    data = yaml.safe_load(substituted)
    return data or {}


def load_config(path: str | Path) -> AppConfig:
    """从 YAML 文件加载并校验为 :class:`AppConfig`。"""
    return AppConfig.model_validate(load_yaml(path))


def dump_config_yaml(config: AppConfig) -> str:
    """把 :class:`AppConfig` 序列化为 YAML 文本。"""
    data = config.model_dump()
    return yaml.dump(
        data,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )
