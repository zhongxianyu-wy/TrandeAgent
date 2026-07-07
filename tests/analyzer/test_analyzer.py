"""T06/T09/T11: FundAnalyzer 抽象 + DefaultAnalyzer 主流程/标签/降级 测试。"""
from __future__ import annotations

import pytest

from src.analyzer.analyzer import (
    DefaultAnalyzer,
    FundAnalyzer,
    flatten_metrics,
    label_from_rating,
)
from src.analyzer.models import FundReport
from tests.analyzer.conftest import (
    FakeIndicatorEngine,
    MockLLMClient,
    make_indicators,
    valid_llm_response,
)


class TestAbstractInterface:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            FundAnalyzer()  # type: ignore[abstract]


class TestFlattenMetrics:
    def test_contains_all_layers(self, indicators):
        m = flatten_metrics(indicators)
        # L1
        assert "scale" in m and "manager_tenure_years" in m
        # L2
        assert "sharpe" in m and "return_1y" in m and "max_drawdown" in m
        # L3
        assert "style_box" in m
        # L4
        assert "share_change_yoy" in m
        # rating
        assert "rating" in m
        assert m["rating"] == 4

    def test_values_match_indicators(self, indicators):
        m = flatten_metrics(indicators)
        assert m["scale"] == indicators.l1_basic.scale
        assert m["sharpe"] == indicators.l2_performance.sharpe


class TestLabelFromRating:
    """T11 标签判断。"""

    @pytest.mark.parametrize("rating,expected", [
        (5, "建议"),
        (4, "建议"),
        (3, "中性"),
        (0, "中性"),  # 未评级
        (2, "回避"),
        (1, "回避"),
    ])
    def test_thresholds(self, rating, expected):
        assert label_from_rating(rating) == expected


class TestAnalyzeHappyPath:
    """T09 主流程：指标 → LLM → 后校验通过。"""

    def test_returns_valid_report(self, fake_engine, valid_response):
        llm = MockLLMClient([valid_response])
        analyzer = DefaultAnalyzer(fake_engine, llm, max_retries=1)
        report = analyzer.analyze("000001")

        assert isinstance(report, FundReport)
        assert report.fund_code == "000001"
        assert report.degraded is False
        assert report.label == "建议"
        assert report.recommendation_pool is True
        # 7 章节
        assert len(report.sections) == 7
        # citations 已填充
        assert len(report.citations) > 0
        # 引擎被调用一次
        assert len(fake_engine.calls) == 1
        # LLM 被调用一次（首次即通过）
        assert len(llm.calls) == 1

    def test_metrics_json_passed_to_llm(self, fake_engine, valid_response):
        llm = MockLLMClient([valid_response])
        analyzer = DefaultAnalyzer(fake_engine, llm)
        analyzer.analyze("000001")
        _prompt, metrics_json = llm.calls[0]
        assert "sharpe" in metrics_json
        assert "scale" in metrics_json

    def test_last_validation_stored(self, fake_engine, valid_response):
        llm = MockLLMClient([valid_response])
        analyzer = DefaultAnalyzer(fake_engine, llm)
        analyzer.analyze("000001")
        assert analyzer.last_validation is not None
        assert analyzer.last_validation.valid is True
        assert analyzer.last_validation.citations_checked >= 1


class TestRetryOnValidationFailure:
    """后校验失败 → 重试 1 次。"""

    def test_retry_succeeds(self, fake_engine, valid_response):
        bad = {
            "fund_code": "000001",
            "one_liner": "必涨【依据：future_return=200%】",
            "label": "建议",
            "sections": [
                {"title": t, "content": "【依据：future_return=200%】"}
                for t in (
                    "经理画像", "业绩归因", "风格分析", "现金流",
                    "风险提示", "综合评估", "观察池建议",
                )
            ],
        }
        llm = MockLLMClient([bad, valid_response])
        analyzer = DefaultAnalyzer(fake_engine, llm, max_retries=1)
        report = analyzer.analyze("000001")
        assert report.degraded is False
        assert len(llm.calls) == 2

    def test_retry_on_llm_exception(self, fake_engine, valid_response):
        """LLM 调用抛异常 → 重试。"""
        llm = MockLLMClient([RuntimeError("net error"), valid_response])
        analyzer = DefaultAnalyzer(fake_engine, llm, max_retries=1)
        report = analyzer.analyze("000001")
        assert report.degraded is False
        assert len(llm.calls) == 2


class TestDegradeToRuleBased:
    """后校验持续失败 → 降级到规则评级。"""

    def test_degrade_after_retries(self, fake_engine):
        bad = {
            "fund_code": "000001",
            "one_liner": "必涨【依据：future_return=200%】",
            "label": "建议",
            "sections": [{"title": "经理画像", "content": "【依据：future_return=200%】"}],
        }
        llm = MockLLMClient([bad, dict(bad)])
        analyzer = DefaultAnalyzer(fake_engine, llm, max_retries=1)
        report = analyzer.analyze("000001")

        assert report.degraded is True
        # 降级报告基于 rating=4 → 建议
        assert report.label == "建议"
        assert report.recommendation_pool is True
        # 降级报告引用全部真实 → 自校验通过
        assert analyzer.validate_citations(report, flatten_metrics(make_indicators()))

    def test_degrade_label_from_low_rating(self):
        indicators = make_indicators(rating=2)
        engine = FakeIndicatorEngine(indicators)
        llm = MockLLMClient([])  # 直接返回空 → 无引用 → 失败
        analyzer = DefaultAnalyzer(engine, llm, max_retries=0)
        report = analyzer.analyze("000001")
        assert report.degraded is True
        assert report.label == "回避"
        assert report.recommendation_pool is False

    def test_degraded_report_has_seven_sections(self, fake_engine):
        llm = MockLLMClient([])
        analyzer = DefaultAnalyzer(fake_engine, llm, max_retries=0)
        report = analyzer.analyze("000001")
        assert len(report.sections) == 7


class TestBuildReportRobustness:
    """LLM 返回字段不规范时的容错。"""

    def test_invalid_label_defaults_neutral(self, fake_engine):
        raw = valid_llm_response()
        raw["label"] = "强烈推荐"  # 非法
        llm = MockLLMClient([raw])
        analyzer = DefaultAnalyzer(fake_engine, llm)
        report = analyzer.analyze("000001")
        assert report.label == "中性"

    def test_missing_sections_padded(self, fake_engine):
        raw = {
            "fund_code": "000001",
            "one_liner": "结论【依据：sharpe=1.2】",
            "label": "中性",
            "sections": [{"title": "经理画像", "content": "任期【依据：manager_tenure_years=6.5】"}],
        }
        llm = MockLLMClient([raw])
        analyzer = DefaultAnalyzer(fake_engine, llm)
        report = analyzer.analyze("000001")
        # 补齐到 7 章节
        assert len(report.sections) == 7

    def test_non_dict_response_degrades(self, fake_engine):
        llm = MockLLMClient(["not a dict", "still not"])  # type: ignore[list-item]
        analyzer = DefaultAnalyzer(fake_engine, llm, max_retries=1)
        report = analyzer.analyze("000001")
        assert report.degraded is True


class TestValidateCitations:
    def test_returns_bool(self, fake_engine, valid_response, metrics):
        llm = MockLLMClient([valid_response])
        analyzer = DefaultAnalyzer(fake_engine, llm)
        report = analyzer.analyze("000001")
        assert isinstance(analyzer.validate_citations(report, metrics), bool)


class TestRenderCardDelegate:
    def test_render_card(self, fake_engine, valid_response):
        llm = MockLLMClient([valid_response])
        analyzer = DefaultAnalyzer(fake_engine, llm)
        report = analyzer.analyze("000001")
        card = analyzer.render_card(report)
        assert "header" in card and "elements" in card
        assert card["header"]["template"] == "green"
