"""8 位投资大师心智模型加载器（T03）。

从 ``config/mind_models.yaml`` 加载原文要点。防幻觉：加载后即冻结为
ground truth，生成器只能引用，不得让 LLM 二次发挥。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from pydantic import BaseModel, Field


class MindModel(BaseModel):
    """单位大师心智模型档案。"""

    id: str
    name: str
    works: list[str] = Field(default_factory=list)
    principles: list[str] = Field(default_factory=list)
    strategy_mapping: str = ""
    domain: list[str] = Field(default_factory=list)


def _project_root() -> Path:
    # src/arena/mind_models/loader.py -> 项目根
    return Path(__file__).resolve().parents[3]


def load_mind_models(path: str | Path | None = None) -> list[MindModel]:
    """从 YAML 加载大师心智模型列表。"""
    if path is None:
        path = _project_root() / "config" / "mind_models.yaml"
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    raw_masters: list[dict[str, Any]] = data.get("masters", []) or []
    return [MindModel(**m) for m in raw_masters]


def load_mind_model_dicts(path: str | Path | None = None) -> list[dict[str, Any]]:
    """以原始 dict 形式加载（供生成器作为 ground-truth 上下文）。"""
    if path is None:
        path = _project_root() / "config" / "mind_models.yaml"
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return list(data.get("masters", []) or [])


def load_prototype_dicts(path: str | Path | None = None) -> list[dict[str, Any]]:
    """从 strategy_prototypes.yaml 加载原型原始 dict 列表。"""
    if path is None:
        path = _project_root() / "config" / "strategy_prototypes.yaml"
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return list(data.get("prototypes", []) or [])


def load_arena_config(path: str | Path | None = None) -> dict[str, Any]:
    """加载 arena.yaml 总配置。"""
    if path is None:
        path = _project_root() / "config" / "arena.yaml"
    return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
