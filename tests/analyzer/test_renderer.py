"""T08: 渲染器测试（Markdown + 飞书卡片）。"""
from __future__ import annotations

from src.analyzer.models import Citation, FundReport, ReportSection
from src.analyzer.renderer import label_color, render_card, render_markdown


def _sample_report(label: str = "建议", degraded: bool = False) -> FundReport:
    return FundReport(
        fund_code="000001",
        one_liner="绩优基【依据：sharpe=1.2】",
        label=label,  # type: ignore[arg-type]
        sections=[
            ReportSection(title="经理画像", content="任期长【依据：manager_tenure_years=6.5】"),
            ReportSection(title="业绩归因", content="收益好"),
        ],
        recommendation_pool=(label == "建议"),
        citations=[Citation(metric_name="sharpe", value="1.2", location="一句话结论")],
        degraded=degraded,
    )


class TestRenderMarkdown:
    def test_contains_fund_code_and_label(self):
        md = render_markdown(_sample_report())
        assert "000001" in md
        assert "建议" in md
        assert "绩优基" in md

    def test_contains_sections(self):
        md = render_markdown(_sample_report())
        assert "## 经理画像" in md
        assert "## 业绩归因" in md

    def test_citation_count(self):
        md = render_markdown(_sample_report())
        assert "1 条指标引用" in md

    def test_degraded_banner(self):
        md = render_markdown(_sample_report(degraded=True))
        assert "降级" in md

    def test_recommendation_pool(self):
        md = render_markdown(_sample_report("回避"))
        assert "暂不进观察池" in md


class TestRenderCard:
    def test_header_structure(self):
        card = render_card(_sample_report())
        assert card["header"]["template"] == "green"  # 建议 → green
        assert card["header"]["title"]["content"] == "000001 · 建议"

    def test_label_colors(self):
        assert render_card(_sample_report("建议"))["header"]["template"] == "green"
        assert render_card(_sample_report("中性"))["header"]["template"] == "blue"
        assert render_card(_sample_report("回避"))["header"]["template"] == "red"

    def test_elements_contain_markdown_and_hr(self):
        card = render_card(_sample_report())
        tags = [e["tag"] for e in card["elements"]]
        assert "markdown" in tags
        assert "hr" in tags

    def test_section_content_in_card(self):
        card = render_card(_sample_report())
        joined = "".join(e.get("content", "") for e in card["elements"])
        assert "经理画像" in joined
        assert "任期长" in joined

    def test_feishu_card_schema_compatible(self):
        """卡片 dict 结构对齐 #2 feishu-io FeishuCard（header + elements）。"""
        from src.feishu.cards import FeishuCard

        card = render_card(_sample_report())
        # FeishuCard 校验通过即结构合法
        validated = FeishuCard(**card)
        assert validated.header["template"] == "green"
        assert len(validated.elements) > 0


class TestLabelColor:
    def test_mapping(self):
        assert label_color("建议") == "green"
        assert label_color("中性") == "blue"
        assert label_color("回避") == "red"
