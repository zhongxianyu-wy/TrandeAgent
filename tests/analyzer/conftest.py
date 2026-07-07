"""pytest fixtures（Feature #6 fund-analyzer）。

提供 mock 指标 / FakeIndicatorEngine / MockLLMClient，不依赖真实网络与 LLM。
"""
from __future__ import annotations

from datetime import date

import pytest

from src.analyzer.llm.client import LLMClient
from src.analyzer.models import FundReport, ReportSection
from src.indicators.engine import IndicatorEngine
from src.indicators.models import (
    FundIndicators,
    L1Basic,
    L2Performance,
    L3Style,
    L4Cashflow,
)


def make_indicators(
    *,
    fund_code: str = "000001",
    rating: int = 4,
) -> FundIndicators:
    """构造一份代表性 FundIndicators（含 L1-L4）。"""
    return FundIndicators(
        fund_code=fund_code,
        as_of_date=date(2026, 7, 4),
        l1_basic=L1Basic(
            scale=27.3,
            establish_years=24.5,
            manager_tenure_years=6.5,
            institution_holding_pct=0.4,
            management_fee=0.015,
            custodian_fee=0.0025,
        ),
        l2_performance=L2Performance(
            return_1y=0.152,
            return_3y=0.30,
            return_5y=0.55,
            rank_1y_percentile=0.20,
            max_drawdown=-0.18,
            sharpe=1.2,
            volatility=0.19,
            alpha=0.03,
            beta=0.95,
        ),
        l3_style=L3Style(
            style_box="大盘成长",
            industry_concentration_top3=0.62,
            holding_turnover=1.5,
            style_drift_score=0.25,
        ),
        l4_cashflow=L4Cashflow(
            share_change_yoy=0.08,
            institution_holding_change=0.03,
            dividend_count_5y=4,
        ),
        rating=rating,
    )


class FakeIndicatorEngine(IndicatorEngine):
    """内存版 IndicatorEngine，返回固定指标，记录调用。"""

    def __init__(self, indicators: FundIndicators) -> None:
        self._indicators = indicators
        self.calls: list[tuple] = []

    def calc_all(self, fund_code: str, end: date, years: int = 5) -> FundIndicators:
        self.calls.append((fund_code, end, years))
        ind = self._indicators.model_copy(deep=True)
        ind.fund_code = fund_code
        ind.as_of_date = end
        return ind

    def calc_batch(self, fund_codes: list[str], end: date, years: int = 5):
        raise NotImplementedError

    def get_rating(self, indicators: FundIndicators) -> int:
        return indicators.rating


class MockLLMClient(LLMClient):
    """按预设序列返回 LLM 响应的 mock（支持抛异常、模拟重试）。"""

    def __init__(self, responses: list) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    def analyze_fund(self, prompt: str, metrics_json: str) -> dict:
        self.calls.append((prompt, metrics_json))
        if not self._responses:
            return {}
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def valid_llm_response(fund_code: str = "000001") -> dict:
    """一份引用全部真实且数值一致的合法 LLM 响应。"""
    return {
        "fund_code": fund_code,
        "one_liner": f"绩优成长基，夏普优秀【依据：sharpe=1.2】",
        "label": "建议",
        "sections": [
            {"title": "经理画像", "content": "经理任期6.5年，经验丰富【依据：manager_tenure_years=6.5】"},
            {"title": "业绩归因", "content": "近1年收益15.2%，同类靠前【依据：return_1y=0.152】"},
            {"title": "风格分析", "content": "大盘成长风格【依据：style_box=大盘成长】"},
            {"title": "现金流", "content": "份额持续增长【依据：share_change_yoy=0.08】"},
            {"title": "风险提示", "content": "回撤可控【依据：max_drawdown=-0.18】"},
            {"title": "综合评估", "content": "评级4星【依据：rating=4】"},
            {"title": "观察池建议", "content": "建议进入观察池【依据：rating=4】"},
        ],
        "recommendation_pool": True,
    }


@pytest.fixture
def indicators() -> FundIndicators:
    return make_indicators()


@pytest.fixture
def metrics(indicators) -> dict:
    from src.analyzer.analyzer import flatten_metrics

    return flatten_metrics(indicators)


@pytest.fixture
def fake_engine(indicators) -> FakeIndicatorEngine:
    return FakeIndicatorEngine(indicators)


@pytest.fixture
def valid_response() -> dict:
    return valid_llm_response()


def make_report(
    *,
    fund_code: str = "000001",
    label: str = "中性",
    with_citations: bool = True,
    degraded: bool = False,
) -> FundReport:
    """构造测试用 FundReport（with_citations=False 可造无引用报告）。"""
    if with_citations:
        content = "经理任期长【依据：manager_tenure_years=6.5】"
        one_liner = "结论【依据：sharpe=1.2】"
    else:
        content = "该基金经理经验丰富，无数据引用。"
        one_liner = "该基金表现尚可。"
    return FundReport(
        fund_code=fund_code,
        one_liner=one_liner,
        label=label,  # type: ignore[arg-type]
        sections=[ReportSection(title="经理画像", content=content)],
        recommendation_pool=(label == "建议"),
        degraded=degraded,
    )
