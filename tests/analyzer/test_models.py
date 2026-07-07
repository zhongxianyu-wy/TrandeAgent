"""T05: FundReport / ReportSection / Citation 模型测试。"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.analyzer.models import Citation, FundReport, ReportSection


class TestReportSection:
    def test_basic(self):
        s = ReportSection(title="经理画像", content="任期长【依据：x=1】")
        assert s.title == "经理画像"
        assert "【依据" in s.content


class TestFundReport:
    def test_defaults(self):
        r = FundReport(fund_code="000001", one_liner="ok", label="中性")
        assert r.fund_code == "000001"
        assert r.sections == []
        assert r.citations == []
        assert r.recommendation_pool is False
        assert r.degraded is False

    def test_label_constraint(self):
        """label 仅允许三选一。"""
        with pytest.raises(ValidationError):
            FundReport(fund_code="x", one_liner="y", label="强烈推荐")  # type: ignore[arg-type]

    def test_full_construction(self):
        r = FundReport(
            fund_code="000001",
            one_liner="结论",
            label="建议",
            sections=[ReportSection(title="t", content="c")],
            recommendation_pool=True,
            citations=[Citation(metric_name="sharpe", value="1.2", location="一句话结论")],
            degraded=False,
        )
        assert r.label == "建议"
        assert r.citations[0].metric_name == "sharpe"


class TestCitation:
    def test_fields(self):
        c = Citation(metric_name="sharpe", value="1.2", location="综合评估")
        assert c.metric_name == "sharpe"
        assert c.value == "1.2"
        assert c.location == "综合评估"
