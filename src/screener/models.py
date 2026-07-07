"""Pydantic 规则模型（T01）。

对应 plan §2 数据模型。规则全部 YAML 化，用户可读可改。
字段路径用点号分隔，如 "l2_performance.sharpe"，既支持嵌套 FundIndicators
写法，也兼容 calc_batch 返回的扁平列名 "sharpe"。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator

# 支持的操作符
Operator = Literal[">=", "<=", "between", "in", "percentile_top"]


class Rule(BaseModel):
    """单条筛选规则。"""

    name: str  # 规则名（唯一，用于权重映射与解释）
    field: str  # 对应 FundIndicators 字段路径，如 "l2_performance.sharpe"
    op: Operator  # 操作符
    value: Any = None  # 阈值：float / list / str

    @field_validator("value")
    @classmethod
    def _check_value(cls, v: Any) -> Any:
        # between / in 需要 list；其余需要标量
        # 具体语义校验放在运算符内做，这里仅放宽 Any 默认
        return v


class ScreenerConfig(BaseModel):
    """筛选配置：规则集合 + 权重 + Top-N。"""

    rules: list[Rule]
    weights: dict[str, float] = Field(default_factory=dict)  # rule name -> weight
    top_n: int = 20

    @field_validator("top_n")
    @classmethod
    def _top_n_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("top_n 必须 >= 1")
        return v

    def weight_of(self, name: str) -> float:
        """取规则权重，缺省默认 1.0。"""
        return self.weights.get(name, 1.0)


class ScreenResult(BaseModel):
    """单只基金筛选结果。"""

    fund_code: str
    score: float
    matched_rules: list[str]


def load_yaml_config(path: str | Path) -> ScreenerConfig:
    """从 YAML 文件加载默认筛选配置（顶层 rules/weights/top_n）。"""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return ScreenerConfig(**data)


def load_yaml_presets(path: str | Path) -> dict[str, ScreenerConfig]:
    """从 YAML 文件加载命名预设集合（presets 段）。"""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    presets_raw = data.get("presets", {}) or {}
    presets: dict[str, ScreenerConfig] = {}
    for name, body in presets_raw.items():
        presets[name] = ScreenerConfig(**(body or {}))
    return presets
