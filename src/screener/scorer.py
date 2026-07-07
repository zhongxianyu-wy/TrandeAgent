"""综合得分（T08）。

综合得分 = 命中规则数 × 权重之和（plan §6 关键决策）。
每条规则命中得 1 次，按配置权重加权累加。
"""
from __future__ import annotations

from src.screener.models import ScreenerConfig


def score_fund(matched_rules: list[str], config: ScreenerConfig) -> float:
    """单只基金综合得分：命中规则权重之和。

    缺省权重默认 1.0。
    """
    return sum(config.weight_of(name) for name in matched_rules)
