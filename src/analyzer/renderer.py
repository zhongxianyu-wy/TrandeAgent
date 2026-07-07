"""报告渲染（T08）：Markdown + 飞书交互卡片。

Markdown 用于本地查看/日志，卡片 dict 结构对齐 #2 feishu-io 的 FeishuCard
（header + elements），可直接推送飞书单聊。
"""
from __future__ import annotations

from src.analyzer.models import FundReport, ReportLabel

# 标签 → 飞书卡片 header 模板色
_LABEL_TEMPLATE: dict[ReportLabel, str] = {
    "建议": "green",
    "中性": "blue",
    "回避": "red",
}

# 标签 → 中文徽标
_LABEL_BADGE: dict[ReportLabel, str] = {
    "建议": "✅ 建议",
    "中性": "➖ 中性",
    "回避": "🚫 回避",
}


def render_markdown(report: FundReport) -> str:
    """渲染为 Markdown 文本。"""
    lines: list[str] = []
    lines.append(f"# {report.fund_code} 基金分析报告")
    lines.append("")
    lines.append(f"> {report.one_liner}")
    lines.append("")
    lines.append(f"**标签**：{_LABEL_BADGE.get(report.label, report.label)}")
    pool = "✅ 建议进观察池" if report.recommendation_pool else "❌ 暂不进观察池"
    lines.append(f"**观察池**：{pool}")
    if report.degraded:
        lines.append("")
        lines.append("> ⚠️ 本报告因后校验未通过，已降级为规则评级生成。")
    lines.append("")
    lines.append("---")
    for section in report.sections:
        lines.append("")
        lines.append(f"## {section.title}")
        lines.append("")
        lines.append(section.content)
    lines.append("")
    lines.append("---")
    lines.append(
        f"*共 {len(report.citations)} 条指标引用，每条结论均可追溯至输入指标。*"
    )
    return "\n".join(lines)


def render_card(report: FundReport) -> dict:
    """渲染为飞书交互卡片 dict（对齐 FeishuCard header + elements 结构）。"""
    template = _LABEL_TEMPLATE.get(report.label, "blue")
    elements: list[dict] = [
        {
            "tag": "markdown",
            "content": (
                f"**{_LABEL_BADGE.get(report.label, report.label)}** · "
                f"{report.one_liner}\n"
                f"观察池：{'建议进入' if report.recommendation_pool else '暂不进入'}"
                + ("  ⚠️已降级为规则评级" if report.degraded else "")
            ),
        },
        {"tag": "hr"},
    ]

    for section in report.sections:
        elements.append(
            {"tag": "markdown", "content": f"**{section.title}**\n{section.content}"}
        )
        elements.append({"tag": "hr"})

    elements.append(
        {
            "tag": "markdown",
            "content": (
                f"共 {len(report.citations)} 条指标引用 · "
                "每条结论可追溯至输入指标"
            ),
        }
    )

    return {
        "header": {
            "template": template,
            "title": {
                "tag": "plain_text",
                "content": f"{report.fund_code} · {report.label}",
            },
        },
        "elements": elements,
    }


def label_color(label: ReportLabel) -> str:
    """暴露标签配色，便于外部复用。"""
    return _LABEL_TEMPLATE.get(label, "blue")
