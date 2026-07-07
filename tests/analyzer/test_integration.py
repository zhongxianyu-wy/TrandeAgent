"""T13: 集成测试 —— 端到端 analyze → validate → render。"""
from __future__ import annotations

import pytest

from src.analyzer.analyzer import DefaultAnalyzer, flatten_metrics
from src.analyzer.renderer import render_card, render_markdown
from src.analyzer.validator import check_citations
from tests.analyzer.conftest import (
    FakeIndicatorEngine,
    MockLLMClient,
    make_indicators,
    valid_llm_response,
)


@pytest.fixture
def integrated_analyzer(fake_engine):
    """默认走 LLM 合规路径的 analyzer。"""
    llm = MockLLMClient([valid_llm_response()])
    return DefaultAnalyzer(fake_engine, llm, max_retries=1)


class TestEndToEnd:
    def test_analyze_validate_render(self, integrated_analyzer, metrics):
        report = integrated_analyzer.analyze("000001")

        # 1. 报告结构完整
        assert report.fund_code == "000001"
        assert report.label in ("建议", "中性", "回避")
        assert len(report.sections) == 7

        # 2. 后校验通过（无幻觉）
        result = check_citations(report, metrics)
        assert result.valid, f"后校验失败：{result.errors}"

        # 3. Markdown 渲染
        md = render_markdown(report)
        assert "000001" in md
        assert all(s.title in md for s in report.sections)

        # 4. 卡片渲染对齐 FeishuCard schema
        card = render_card(report)
        from src.feishu.cards import FeishuCard

        FeishuCard(**card)  # 结构合法不抛异常

    def test_every_section_has_traceable_citation(self, integrated_analyzer, metrics):
        """AC-2：每条结论可追溯到指标。"""
        report = integrated_analyzer.analyze("000001")
        result = check_citations(report, metrics)
        assert result.citations_checked >= len(report.sections)

    def test_label_consistent_with_rating(self):
        """标签与规则评级一致（合规 LLM 响应 label=建议，rating=4）。"""
        engine = FakeIndicatorEngine(make_indicators(rating=4))
        llm = MockLLMClient([valid_llm_response()])
        analyzer = DefaultAnalyzer(engine, llm)
        report = analyzer.analyze("000001")
        assert report.label == "建议"


class TestDegradedEndToEnd:
    def test_degraded_report_still_passes_self_validation(self, fake_engine):
        """降级报告必须 100% 通过后校验（引用全真实）。"""
        llm = MockLLMClient([])  # 无引用 → 失败 → 降级
        analyzer = DefaultAnalyzer(fake_engine, llm, max_retries=0)
        report = analyzer.analyze("000001")
        assert report.degraded is True
        result = check_citations(report, flatten_metrics(make_indicators()))
        assert result.valid, f"降级报告引用错误：{result.errors}"
        assert result.citations_checked > 0

    def test_degraded_renders(self, fake_engine):
        llm = MockLLMClient([])
        analyzer = DefaultAnalyzer(fake_engine, llm, max_retries=0)
        report = analyzer.analyze("000001")
        md = render_markdown(report)
        card = render_card(report)
        assert "降级" in md
        assert "header" in card


class TestLabelMatrix:
    """三种标签的端到端路径。"""

    @pytest.mark.parametrize("rating,expected_label,pool", [
        (4, "建议", True),
        (3, "中性", False),
        (2, "回避", False),
    ])
    def test_degraded_label_matrix(self, rating, expected_label, pool):
        engine = FakeIndicatorEngine(make_indicators(rating=rating))
        llm = MockLLMClient([])
        analyzer = DefaultAnalyzer(engine, llm, max_retries=0)
        report = analyzer.analyze("000001")
        assert report.degraded is True
        assert report.label == expected_label
        assert report.recommendation_pool is pool
