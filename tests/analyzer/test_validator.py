"""T07: 后校验单元测试（citation 存在性 + 数值一致性）。"""
from __future__ import annotations

import pytest

from src.analyzer.models import FundReport, ReportSection
from src.analyzer.validator import (
    CITATION_PATTERN,
    check_citations,
    extract_citations,
)

METRICS = {
    "sharpe": 1.2,
    "return_1y": 0.152,
    "max_drawdown": -0.18,
    "rating": 4,
    "style_box": "大盘成长",
    "manager_tenure_years": 6.5,
}


def _report(one_liner: str, sections: list[tuple[str, str]]) -> FundReport:
    return FundReport(
        fund_code="000001",
        one_liner=one_liner,
        label="建议",
        sections=[ReportSection(title=t, content=c) for t, c in sections],
    )


class TestExtractCitations:
    def test_chinese_colon(self):
        text = "结论【依据：sharpe=1.2】"
        assert extract_citations(text) == [("sharpe", "1.2")]

    def test_english_colon(self):
        text = "结论【依据:sharpe=1.2】"
        assert extract_citations(text) == [("sharpe", "1.2")]

    def test_negative_value(self):
        text = "回撤【依据：max_drawdown=-0.18】"
        assert extract_citations(text) == [("max_drawdown", "-0.18")]

    def test_multiple(self):
        text = "a【依据：sharpe=1.2】 b【依据：rating=4】"
        assert extract_citations(text) == [("sharpe", "1.2"), ("rating", "4")]

    def test_none(self):
        assert extract_citations("无引用") == []

    def test_pattern_compiled(self):
        assert CITATION_PATTERN.search("【依据：x=1】") is not None


class TestCheckCitationsValid:
    def test_all_valid(self):
        r = _report(
            "绩优【依据：sharpe=1.2】",
            [("综合评估", "评级【依据：rating=4】")],
        )
        result = check_citations(r, METRICS)
        assert result.valid is True
        assert result.citations_checked == 2
        assert result.errors == []

    def test_percentage_form_accepted(self):
        """引用写 15.2%（真实值 0.152）应通过。"""
        r = _report("收益【依据：return_1y=15.2%】", [])
        result = check_citations(r, METRICS)
        assert result.valid is True

    def test_decimal_form_accepted(self):
        r = _report("收益【依据：return_1y=0.152】", [])
        assert check_citations(r, METRICS).valid is True

    def test_negative_match(self):
        r = _report("回撤【依据：max_drawdown=-0.18】", [])
        assert check_citations(r, METRICS).valid is True

    def test_string_metric_exact(self):
        r = _report("风格【依据：style_box=大盘成长】", [])
        assert check_citations(r, METRICS).valid is True

    def test_one_liner_scanned(self):
        """一句话结论中的引用也参与校验。"""
        r = _report("结论【依据：sharpe=99.9】", [])
        result = check_citations(r, METRICS)
        assert result.valid is False


class TestCheckCitationsInvalid:
    def test_fabricated_metric_name(self):
        """编造不存在的指标。"""
        r = _report("结论【依据：fake_metric=0.5】", [])
        result = check_citations(r, METRICS)
        assert result.valid is False
        assert "fake_metric" in result.hallucinated_metrics
        assert any("编造指标" in e for e in result.errors)

    def test_wrong_numeric_value(self):
        """指标存在但数值不一致（幻觉）。"""
        r = _report("结论【依据：sharpe=99.9】", [])
        result = check_citations(r, METRICS)
        assert result.valid is False
        assert any("数值不一致" in e for e in result.errors)

    def test_string_mismatch(self):
        r = _report("风格【依据：style_box=小盘价值】", [])
        result = check_citations(r, METRICS)
        assert result.valid is False

    def test_no_citations_at_all(self):
        """无任何引用 → 未遵守规则，不可信。"""
        r = _report("该基金不错。", [("综合评估", "整体稳健。")])
        result = check_citations(r, METRICS)
        assert result.valid is False
        assert any("未包含任何" in e for e in result.errors)

    def test_partial_invalid(self):
        """部分引用合法、部分幻觉 → 整体不通过。"""
        r = _report(
            "结论【依据：sharpe=1.2】",
            [("风险", "编造【依据：ghost=3】")],
        )
        result = check_citations(r, METRICS)
        assert result.valid is False
        assert "ghost" in result.hallucinated_metrics
        assert result.citations_checked == 2


class TestValidationResultBool:
    def test_truthy_when_valid(self):
        r = _report("结论【依据：sharpe=1.2】", [])
        assert bool(check_citations(r, METRICS)) is True
