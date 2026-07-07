"""强约束 prompt 模板（T04 / ADR-005 第一层防御）。

System Prompt 明确"唯一事实来源是输入指标 JSON"，强制每条结论以
【依据：指标名=数值】引用，证据不足输出"数据不足"。
User Prompt 用 jinja2 渲染基金代码，指标 JSON 由 client 注入。
"""
from __future__ import annotations

from jinja2 import Template

# 报告固定 7 章节（spec FR-1）
REPORT_SECTIONS: tuple[str, ...] = (
    "经理画像",
    "业绩归因",
    "风格分析",
    "现金流",
    "风险提示",
    "综合评估",
    "观察池建议",
)

# 强约束系统提示（防幻觉第一层：Prompt 层）
SYSTEM_PROMPT = (
    "你是基金分析专家。你的唯一事实来源是用户提供的指标 JSON，"
    "严禁编造任何未在 JSON 中出现的指标名或数值。\n\n"
    "【输出规则】\n"
    "1. 每条结论必须以【依据：指标名=数值】结尾引用证据，"
    "指标名与数值必须与输入 JSON 完全一致（不可四舍五入到失真）。\n"
    '2. 证据不足时直接写「数据不足」，不要臆测或编造。\n'
    "3. 必须输出合法 JSON（不要 markdown 代码块），结构如下：\n"
    '{\n'
    '  "fund_code": "基金代码",\n'
    '  "one_liner": "一句话结论（含一个依据引用）",\n'
    '  "label": "建议" | "中性" | "回避",\n'
    '  "sections": [\n'
    '    {"title": "经理画像", "content": "中文分析...【依据：指标名=数值】"},\n'
    "    ... 共 7 个章节，标题固定\n"
    "  ],\n"
    '  "recommendation_pool": true | false\n'
    "}\n"
    "4. sections 必须恰好 7 章，标题依次为："
    + "、".join(REPORT_SECTIONS)
    + "。\n"
    "5. label 仅允许「建议」「中性」「回避」三选一，不可缺失。\n"
    "6. recommendation_pool：建议=进观察池 true，其余 false。"
)

# 用户指令模板（基金代码部分用 jinja2 渲染；指标 JSON 由 client 拼接）
_USER_PROMPT_TEMPLATE = Template(
    "请分析基金 {{ fund_code }}，基于输入指标生成 7 章节中文报告。\n"
    "记住：每条结论都要用【依据：指标名=数值】引用真实存在的指标，"
    "label 三选一，recommendation_pool 按标签给出。"
)


def build_user_prompt(fund_code: str) -> str:
    """渲染用户指令（不含指标 JSON，JSON 由 client 在调用时拼接）。"""
    return _USER_PROMPT_TEMPLATE.render(fund_code=fund_code)


def estimate_tokens(text: str) -> int:
    """粗略估算 token 数（成本预算预检，NFR：单基金 input ≤ 3K）。

    中文约 1 字 ≈ 1 token，英文约 4 字符 ≈ 1 token，取较大值做保守估计。
    """
    if not text:
        return 0
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    other = len(text) - cjk
    return cjk + max(0, (other + 3) // 4)
