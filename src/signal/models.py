"""信号 schema（T01）。

对应 plan §2 / spec §3 的数据模型。SignalRule 描述单条规则，Signal 描述
某基金某日综合后的四档信号。所有数值字段允许默认值，避免上游数据不全导致整层失败。
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# 信号大类（context.md 边界：技术面 / 基本面 / 基金专属）
SignalCategory = Literal["technical", "fundamental", "fund_specific"]

# 四档信号档位（PRD §6 F4）
SignalLevel = Literal["加仓", "持有", "减仓", "止损"]

# 已支持的指标标识
SignalIndicator = Literal[
    "ma_cross",
    "macd",
    "rsi",
    "bollinger",
    "pe_percentile",
    "drawdown",
    "intraday_alert",
]

# 比较算子
SignalOperator = Literal[
    "cross_above",
    "cross_below",
    "above",
    "below",
    "between",
]


class SignalRule(BaseModel):
    """单条信号规则（来自 config/signals.yaml）。

    Attributes:
        name: 规则中文名（用于理由展示）。
        category: 信号大类。
        indicator: 指标标识，见 SignalIndicator。
        operator: 比较算子。
        threshold: 触发阈值（语义随 indicator 不同：RSI/PE 为百分位、
            回撤为百分比、大跌为百分比、MA/MACD/Bollinger 不使用）。
        weight: 权重，用于 synthesizer 加权合成。
    """

    name: str
    category: SignalCategory
    indicator: SignalIndicator
    operator: SignalOperator
    threshold: float = 0.0
    weight: float = 1.0

    @field_validator("weight")
    @classmethod
    def _weight_positive(cls, v: float) -> float:
        if v < 0:
            raise ValueError("weight 不能为负")
        return v


class Signal(BaseModel):
    """某基金某日的综合信号。

    Attributes:
        fund_code: 基金代码。
        date: 信号日期。
        level: 四档之一（加仓/持有/减仓/止损）。
        reasons: 触发理由列表，每条含【依据：指标=值】。
        score: 加权综合得分（加仓贡献 +weight，减仓贡献 -weight）。
        signals_detail: 各规则的明细（dict 列表，JSON 可序列化）。
    """

    fund_code: str
    date: date
    level: SignalLevel
    reasons: list[str] = Field(default_factory=list)
    score: float = 0.0
    signals_detail: list[dict] = Field(default_factory=list)
