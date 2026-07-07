"""T04: 强约束 prompt 模板测试。"""
from __future__ import annotations

from src.analyzer.llm.prompts import (
    REPORT_SECTIONS,
    SYSTEM_PROMPT,
    build_user_prompt,
    estimate_tokens,
)


class TestSystemPrompt:
    def test_contains_citation_rule(self):
        """防幻觉第一层：prompt 必须强制引用格式。"""
        assert "【依据：指标名=数值】" in SYSTEM_PROMPT
        assert "唯一事实来源" in SYSTEM_PROMPT

    def test_contains_json_schema(self):
        """防幻觉第二层：要求 JSON 输出。"""
        assert "label" in SYSTEM_PROMPT
        assert "recommendation_pool" in SYSTEM_PROMPT

    def test_forbids_fabrication(self):
        assert "数据不足" in SYSTEM_PROMPT

    def test_seven_sections_fixed(self):
        assert len(REPORT_SECTIONS) == 7
        for title in ("经理画像", "业绩归因", "风格分析", "现金流", "风险提示"):
            assert title in REPORT_SECTIONS


class TestUserPrompt:
    def test_renders_fund_code(self):
        prompt = build_user_prompt("161725")
        assert "161725" in prompt
        assert "7 章节" in prompt or "7章" in prompt or "7 个章节" in prompt

    def test_different_codes_distinct(self):
        assert build_user_prompt("000001") != build_user_prompt("000002")


class TestEstimateTokens:
    def test_empty(self):
        assert estimate_tokens("") == 0

    def test_cjk(self):
        # 6 个中文字 ≈ 6 token
        assert estimate_tokens("基金分析报告") == 6

    def test_ascii(self):
        n = estimate_tokens("abcd")  # 4 字符 → 1 token
        assert n >= 1
