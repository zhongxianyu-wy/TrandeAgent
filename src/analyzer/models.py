"""基金分析报告 Pydantic schema（T05）。

对应 plan §2 数据模型与 ADR-005 防幻觉三层防御中的 Schema 层。
报告每个结论必须可追溯到指标：sections[*].content 内含【依据：指标名=数值】引用，
citations 字段集中保存解析出的引用列表供后校验使用。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# 报告标签（FR-3 强制三选一）
ReportLabel = Literal["建议", "中性", "回避"]


class ReportSection(BaseModel):
    """报告单章节。"""

    title: str
    content: str  # 含【依据：指标名=数值】引用，作为防幻觉锚点


class Citation(BaseModel):
    """从报告中解析出的一条指标引用。"""

    metric_name: str  # 引用的指标名（必须存在于输入 metrics）
    value: str  # 引用时写出的数值（文本形式，便于与原值比对）
    location: str  # 在报告中的位置（章节标题）


class FundReport(BaseModel):
    """单只基金的完整分析报告。"""

    fund_code: str
    one_liner: str  # 一句话结论
    label: ReportLabel
    sections: list[ReportSection] = Field(default_factory=list)  # 7 章节
    recommendation_pool: bool = False  # 是否建议进观察池
    citations: list[Citation] = Field(default_factory=list)
    # 标记本报告是否由规则降级生成（后校验失败兜底）
    degraded: bool = False
