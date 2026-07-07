"""AppConfig + ChangeImpact Pydantic schema（T01）。

聚合 #5 筛选规则、#7 信号规则与竞技场配置，形成单一可版本管理的策略配置。
对应 plan §2 数据模型。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from src.screener.models import Rule as ScreenerRule
from src.signal.models import SignalRule


class ArenaSection(BaseModel):
    """竞技场配置子节。"""

    enabled: bool = True
    strategy_count: int = Field(default=100, ge=1)
    backtest_years: int = Field(default=5, ge=1)
    top_n_per_domain: int = Field(default=5, ge=1)


class AppConfig(BaseModel):
    """聚合策略配置：观察池 / 筛选规则 / 信号规则 / 竞技场。"""

    observation_pool: list[str] = Field(default_factory=list)
    screener_rules: list[ScreenerRule] = Field(default_factory=list)
    signal_rules: list[SignalRule] = Field(default_factory=list)
    arena: ArenaSection = Field(default_factory=ArenaSection)

    @field_validator("observation_pool", mode="before")
    @classmethod
    def _coerce_pool_to_str(cls, v: object) -> object:
        # YAML 可能将纯数字基金代码解析为 int/float，统一转 str
        if isinstance(v, list):
            return [str(x) for x in v]
        return v

    @field_validator("observation_pool")
    @classmethod
    def _pool_unique(cls, v: list[str]) -> list[str]:
        # 去重并保持首次出现顺序
        seen: set[str] = set()
        out: list[str] = []
        for code in v:
            if code not in seen:
                seen.add(code)
                out.append(code)
        return out


class ChangeImpact(BaseModel):
    """单类配置变更的影响范围报告。

    Attributes:
        change_type: 变更大类。
        added: 新增项（基金代码 / 规则名 / 字段名）。
        removed: 移除项。
        affected_funds: 受影响的基金代码。
        requires_backtest_rerun: 是否需要重跑回测。
        summary: 人类可读摘要。
    """

    change_type: Literal["screener", "signal", "arena", "pool"]
    added: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    affected_funds: list[str] = Field(default_factory=list)
    requires_backtest_rerun: bool = False
    summary: str = ""
