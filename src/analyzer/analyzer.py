"""FundAnalyzer 抽象接口（T06）+ DefaultAnalyzer 实现（T09 主流程 / T11 标签 / 降级）。

主流程：组装指标（#4）→ 强约束 prompt → LLM（JSON mode）→ 后校验（防幻觉）
       → 失败重试 1 次 → 仍失败降级到规则评级（用 #4 rating）。
对应 plan §3 接口契约、ADR-005 三层防御。
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import date
from typing import Any

from loguru import logger

from src.analyzer.llm import LLMClient, build_user_prompt
from src.analyzer.llm.prompts import REPORT_SECTIONS
from src.analyzer.models import Citation, FundReport, ReportLabel, ReportSection
from src.analyzer.renderer import render_card
from src.analyzer.validator import ValidationResult, check_citations
from src.indicators.engine import IndicatorEngine
from src.indicators.models import FundIndicators

# 标签判定阈值（T11）
_LABEL_FOR_RATING: dict[int, ReportLabel] = {}


def label_from_rating(rating: int) -> ReportLabel:
    """根据 #4 评级给出标签（T11）。

    rating >= 4 → 建议；== 3 → 中性；1-2 → 回避；未评级(0) → 中性。
    """
    if rating == 0:
        return "中性"  # 未评级，不下回避结论
    if rating >= 4:
        return "建议"
    if rating <= 2:
        return "回避"
    return "中性"  # rating == 3


# 展平 FundIndicators 为 指标名 → 值（供 LLM 引用 + 后校验比对）
def flatten_metrics(indicators: FundIndicators) -> dict[str, Any]:
    """把 FundIndicators 拍平为 metric_name → value（后校验与 prompt 共用同一来源）。"""
    l1, l2, l3, l4 = (
        indicators.l1_basic,
        indicators.l2_performance,
        indicators.l3_style,
        indicators.l4_cashflow,
    )
    return {
        "scale": l1.scale,
        "establish_years": l1.establish_years,
        "manager_tenure_years": l1.manager_tenure_years,
        "institution_holding_pct": l1.institution_holding_pct,
        "management_fee": l1.management_fee,
        "custodian_fee": l1.custodian_fee,
        "return_1y": l2.return_1y,
        "return_3y": l2.return_3y,
        "return_5y": l2.return_5y,
        "rank_1y_percentile": l2.rank_1y_percentile,
        "max_drawdown": l2.max_drawdown,
        "sharpe": l2.sharpe,
        "volatility": l2.volatility,
        "alpha": l2.alpha,
        "beta": l2.beta,
        "style_box": l3.style_box,
        "industry_concentration_top3": l3.industry_concentration_top3,
        "holding_turnover": l3.holding_turnover,
        "style_drift_score": l3.style_drift_score,
        "share_change_yoy": l4.share_change_yoy,
        "institution_holding_change": l4.institution_holding_change,
        "dividend_count_5y": l4.dividend_count_5y,
        "rating": indicators.rating,
    }


class FundAnalyzer(ABC):
    """单基金深度分析抽象（plan §3 接口契约）。"""

    @abstractmethod
    def analyze(self, fund_code: str) -> FundReport:
        """分析单只基金，返回含防幻觉引用的 FundReport。"""

    @abstractmethod
    def validate_citations(self, report: FundReport, metrics: dict) -> bool:
        """后校验：报告中所有引用必须真实存在于 metrics。"""

    @abstractmethod
    def render_card(self, report: FundReport) -> dict:
        """渲染为飞书卡片 dict。"""


class DefaultAnalyzer(FundAnalyzer):
    """默认分析器：指标 → LLM → 后校验 → 降级兜底。"""

    def __init__(
        self,
        engine: IndicatorEngine,
        llm: LLMClient,
        end: date | None = None,
        years: int = 5,
        max_retries: int = 1,
    ) -> None:
        self._engine = engine
        self._llm = llm
        self._end = end
        self._years = years
        self._max_retries = max(0, max_retries)
        # 记录最近一次后校验详情，便于调试/断言
        self.last_validation: ValidationResult | None = None

    # ------------------------------------------------------------------
    # 主流程（T09）
    # ------------------------------------------------------------------
    def analyze(self, fund_code: str) -> FundReport:
        end = self._end or date.today()
        indicators = self._engine.calc_all(fund_code, end, self._years)
        metrics = flatten_metrics(indicators)
        metrics_json = json.dumps(metrics, ensure_ascii=False, indent=2, default=str)
        prompt = build_user_prompt(fund_code)

        attempts = self._max_retries + 1
        for attempt in range(1, attempts + 1):
            try:
                raw = self._llm.analyze_fund(prompt, metrics_json)
            except Exception as e:  # noqa: BLE001
                logger.warning("LLM 调用异常（attempt {}/{}）：{}", attempt, attempts, e)
                continue
            report = self._build_report(fund_code, raw)
            if self.validate_citations(report, metrics):
                logger.info("基金 {} 分析完成（attempt={}，引用 {} 条）",
                            fund_code, attempt, self.last_validation.citations_checked)
                return report
            logger.warning(
                "后校验失败（attempt {}/{}）：{}",
                attempt, attempts, self.last_validation.errors[:3],
            )

        # 全部失败 → 降级到规则评级
        logger.warning("基金 {} 后校验持续失败，降级到规则评级", fund_code)
        return self._degrade_to_rule_based(fund_code, indicators, metrics)

    # ------------------------------------------------------------------
    # 后校验入口
    # ------------------------------------------------------------------
    def validate_citations(self, report: FundReport, metrics: dict) -> bool:
        result = check_citations(report, metrics)
        self.last_validation = result
        return result.valid

    # ------------------------------------------------------------------
    # 渲染入口
    # ------------------------------------------------------------------
    def render_card(self, report: FundReport) -> dict:
        return render_card(report)

    # ------------------------------------------------------------------
    # 内部：把 LLM 原始 dict 组装为 FundReport
    # ------------------------------------------------------------------
    def _build_report(self, fund_code: str, raw: dict) -> FundReport:
        if not isinstance(raw, dict):
            raw = {}

        label = self._coerce_label(raw.get("label"))
        one_liner = str(raw.get("one_liner") or "数据不足，无法给出结论。")

        sections = self._coerce_sections(raw.get("sections"))

        recommendation_pool = self._coerce_bool(
            raw.get("recommendation_pool"), default=(label == "建议")
        )

        report = FundReport(
            fund_code=fund_code,
            one_liner=one_liner,
            label=label,
            sections=sections,
            recommendation_pool=recommendation_pool,
        )
        self._populate_citations(report)
        return report

    @staticmethod
    def _coerce_label(value: Any) -> ReportLabel:
        if value in ("建议", "中性", "回避"):
            return value  # type: ignore[return-value]
        return "中性"

    @staticmethod
    def _coerce_bool(value: Any, *, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip() in ("true", "True", "1", "是")
        return default

    @staticmethod
    def _coerce_sections(raw_sections: Any) -> list[ReportSection]:
        if not isinstance(raw_sections, list):
            raw_sections = []
        sections: list[ReportSection] = []
        for item in raw_sections:
            if isinstance(item, ReportSection):
                sections.append(item)
                continue
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            content = str(item.get("content") or "").strip()
            if not title:
                continue
            sections.append(ReportSection(title=title, content=content))
        # 对齐固定 7 章节标题：缺失补占位，多余截断
        aligned: list[ReportSection] = []
        by_title = {s.title: s for s in sections}
        for i, fixed_title in enumerate(REPORT_SECTIONS):
            if fixed_title in by_title:
                aligned.append(by_title[fixed_title])
            elif i < len(sections):
                aligned.append(ReportSection(title=fixed_title, content=sections[i].content))
            else:
                aligned.append(ReportSection(title=fixed_title, content="数据不足。"))
        return aligned

    @staticmethod
    def _populate_citations(report: FundReport) -> None:
        """从 one_liner + sections 解析引用，填充 citations。"""
        from src.analyzer.validator import extract_citations

        citations: list[Citation] = []
        for name, val in extract_citations(report.one_liner):
            citations.append(Citation(metric_name=name, value=val, location="一句话结论"))
        for section in report.sections:
            for name, val in extract_citations(section.content):
                citations.append(Citation(metric_name=name, value=val, location=section.title))
        report.citations = citations

    # ------------------------------------------------------------------
    # 内部：规则评级降级（后校验持续失败兜底）
    # ------------------------------------------------------------------
    def _degrade_to_rule_based(
        self, fund_code: str, indicators: FundIndicators, metrics: dict
    ) -> FundReport:
        """用 #4 rating 生成简单报告（所有引用均来自真实指标，必然通过校验）。"""
        m = metrics
        rating = indicators.rating
        label = label_from_rating(rating)

        def cite(name: str) -> str:
            return f"【依据：{name}={m.get(name)}】"

        sections = [
            ReportSection(
                title="经理画像",
                content=(
                    f"现任经理任期 {m['manager_tenure_years']} 年，"
                    f"基金成立 {m['establish_years']} 年，规模 {m['scale']} 亿元。"
                    + cite("manager_tenure_years") + cite("scale")
                ),
            ),
            ReportSection(
                title="业绩归因",
                content=(
                    f"近 1 年收益 {m['return_1y']:.2%}，夏普 {m['sharpe']:.2f}，"
                    f"同类排名百分位 {m['rank_1y_percentile']:.0%}。"
                    + cite("return_1y") + cite("sharpe")
                ),
            ),
            ReportSection(
                title="风格分析",
                content=(
                    f"风格盒 {m['style_box']}，前 3 行业集中度 "
                    f"{m['industry_concentration_top3']:.0%}。"
                    + cite("style_box") + cite("industry_concentration_top3")
                ),
            ),
            ReportSection(
                title="现金流",
                content=(
                    f"份额同比变动 {m['share_change_yoy']:.0%}，"
                    f"近 5 年分红 {m['dividend_count_5y']} 次。"
                    + cite("share_change_yoy") + cite("dividend_count_5y")
                ),
            ),
            ReportSection(
                title="风险提示",
                content=(
                    f"最大回撤 {m['max_drawdown']:.2%}，年化波动率 {m['volatility']:.2%}。"
                    + cite("max_drawdown") + cite("volatility")
                ),
            ),
            ReportSection(
                title="综合评估",
                content=(
                    f"规则评级 {rating} 星（满分 5）。" + cite("rating")
                ),
            ),
            ReportSection(
                title="观察池建议",
                content=(
                    f"基于规则评级给出标签：{label}。"
                    + cite("rating")
                ),
            ),
        ]

        report = FundReport(
            fund_code=fund_code,
            one_liner=(
                f"规则评级 {rating} 星，标签「{label}」。" + cite("rating")
            ),
            label=label,
            sections=sections,
            recommendation_pool=(label == "建议"),
            degraded=True,
        )
        self._populate_citations(report)
        return report
