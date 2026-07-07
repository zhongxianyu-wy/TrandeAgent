"""T10: 防幻觉专项测试（ADR-005 核心）。

构造 LLM 编造指标 / 错误数值的 JSON 响应，验证后校验能 100% 拦截。
"""
from __future__ import annotations

from src.analyzer.analyzer import DefaultAnalyzer, flatten_metrics
from src.analyzer.models import FundReport, ReportSection
from src.analyzer.validator import check_citations
from tests.analyzer.conftest import (
    FakeIndicatorEngine,
    MockLLMClient,
    make_indicators,
    valid_llm_response,
)

METRICS = flatten_metrics(make_indicators())


def _report(sections: list[tuple[str, str]], one_liner: str = "结论") -> FundReport:
    return FundReport(
        fund_code="000001",
        one_liner=one_liner,
        label="建议",
        sections=[ReportSection(title=t, content=c) for t, c in sections],
    )


class TestFabricatedMetricIntercepted:
    """场景一：LLM 编造一个完全不存在的指标名。"""

    def test_single_fabricated(self):
        r = _report([("综合评估", "未来必涨【依据：future_return=200%】")])
        result = check_citations(r, METRICS)
        assert not result.valid
        assert "future_return" in result.hallucinated_metrics

    def test_multiple_fabricated(self):
        r = _report(
            [
                ("A", "【依据：alpha_prediction=0.9】"),
                ("B", "【依据：moat_score=8.8】"),
            ]
        )
        result = check_citations(r, METRICS)
        assert not result.valid
        assert set(result.hallucinated_metrics) == {"alpha_prediction", "moat_score"}

    def test_mix_real_and_fabricated(self):
        r = _report(
            [
                ("A", "真实【依据：sharpe=1.2】"),
                ("B", "编造【依据：esg_score=99】"),
            ]
        )
        result = check_citations(r, METRICS)
        assert not result.valid
        assert "esg_score" in result.hallucinated_metrics
        assert "sharpe" not in result.hallucinated_metrics


class TestNumericHallucinationIntercepted:
    """场景二：指标名真实，但数值被 LLM 篡改。"""

    def test_inflated_sharpe(self):
        r = _report([("业绩", "夏普极高【依据：sharpe=8.5】")])
        result = check_citations(r, METRICS)
        assert not result.valid
        assert any("数值不一致" in e for e in result.errors)

    def test_downplayed_drawdown(self):
        """把 -18% 回撤美化为 -1%（误导性幻觉）。"""
        r = _report([("风险", "回撤极小【依据：max_drawdown=-0.01】")])
        result = check_citations(r, METRICS)
        assert not result.valid

    def test_rating_inflation(self):
        r = _report([("评估", "五星【依据：rating=5】")])
        result = check_citations(r, METRICS)
        # 真实 rating=4，写成 5 → 拦截
        assert not result.valid


class TestNoCitationIntercepted:
    """场景三：LLM 不遵守引用规则（通篇无依据）。"""

    def test_empty_sections(self):
        r = _report([("A", "该基金表现优秀，值得购买。")])
        result = check_citations(r, METRICS)
        assert not result.valid

    def test_decorative_brackets_not_citation(self):
        """【】但非【依据：...】格式，不应被当作有效引用。"""
        r = _report([("A", "业绩【优秀】值得关注。")])
        result = check_citations(r, METRICS)
        assert not result.valid
        assert result.citations_checked == 0


class TestLegitimateVariationsAccepted:
    """合法的不同数值写法不应被误判为幻觉。"""

    def test_decimal_vs_percentage(self):
        r_dec = _report([("A", "【依据：return_1y=0.152】")])
        r_pct = _report([("A", "【依据：return_1y=15.2%】")])
        assert check_citations(r_dec, METRICS).valid
        assert check_citations(r_pct, METRICS).valid

    def test_integer_value(self):
        """rating=4（int）与引用 4（str）一致。"""
        r = _report([("A", "【依据：rating=4】")])
        assert check_citations(r, METRICS).valid


class TestEndToEndHallucinationFlow:
    """端到端：analyzer 对幻觉 LLM 响应触发重试 → 降级。"""

    def test_retry_then_valid(self, fake_engine):
        """第一次幻觉、第二次合规 → 重试成功，不降级。"""
        bad = {
            "fund_code": "000001",
            "one_liner": "必涨【依据：future_return=200%】",
            "label": "建议",
            "sections": [
                {"title": t, "content": "内容【依据：future_return=200%】"}
                for t in (
                    "经理画像", "业绩归因", "风格分析", "现金流",
                    "风险提示", "综合评估", "观察池建议",
                )
            ],
            "recommendation_pool": True,
        }
        llm = MockLLMClient([bad, valid_llm_response()])
        analyzer = DefaultAnalyzer(fake_engine, llm, max_retries=1)
        report = analyzer.analyze("000001")
        assert report.degraded is False
        assert report.label == "建议"
        assert len(llm.calls) == 2  # 重试了一次

    def test_persistent_hallucination_degrades(self, fake_engine):
        """两次都幻觉 → 降级到规则评级。"""
        bad = {
            "fund_code": "000001",
            "one_liner": "必涨【依据：future_return=200%】",
            "label": "建议",
            "sections": [
                {"title": "经理画像", "content": "【依据：future_return=200%】"}
            ],
            "recommendation_pool": True,
        }
        llm = MockLLMClient([bad, dict(bad)])  # 两次都幻觉
        analyzer = DefaultAnalyzer(fake_engine, llm, max_retries=1)
        report = analyzer.analyze("000001")
        assert report.degraded is True
        # 降级报告引用全部真实 → 自校验通过
        from src.analyzer.validator import check_citations

        assert check_citations(report, flatten_metrics(make_indicators())).valid
