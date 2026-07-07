"""基金筛选器（Feature #5 fund-screener）。

按 YAML 规则对全市场基金指标综合打分排序，输出 Top-N 候选 + 选中理由。
规则字段路径用点号分隔（如 l2_performance.sharpe），支持嵌套 FundIndicators
与 calc_batch 返回的扁平列名两种写法。
"""
from __future__ import annotations

from src.screener.engine import DefaultScreener, FundScreener
from src.screener.models import (
    Operator,
    Rule,
    ScreenResult,
    ScreenerConfig,
    load_yaml_config,
    load_yaml_presets,
)
from src.screener.presets import PRESETS, get_preset, preset_4433, preset_quality
from src.screener.rules import OPERATORS, apply_rule, resolve_field
from src.screener.scorer import score_fund

__all__ = [
    "FundScreener",
    "DefaultScreener",
    "Rule",
    "ScreenerConfig",
    "ScreenResult",
    "Operator",
    "OPERATORS",
    "apply_rule",
    "resolve_field",
    "score_fund",
    "load_yaml_config",
    "load_yaml_presets",
    "preset_4433",
    "preset_quality",
    "PRESETS",
    "get_preset",
]
