"""schema 测试（T02）。"""
from __future__ import annotations

from datetime import date, datetime

from src.api.schema import (
    ApiResponse,
    BusinessError,
    ErrorResponse,
    FundListItem,
    Job,
    JobStatus,
    NavCurve,
    PaginatedData,
    PeriodReturn,
    StrategySummary,
)


def test_api_response_generic():
    resp = ApiResponse(data={"a": 1})
    assert resp.code == 0
    assert resp.message == "ok"
    assert resp.data == {"a": 1}


def test_api_response_default_none():
    resp = ApiResponse()
    assert resp.data is None


def test_job_status_enum():
    assert JobStatus.pending.value == "pending"
    assert JobStatus("running") == JobStatus.running


def test_job_model():
    job = Job(
        job_id="abc",
        type="analyze",
        status=JobStatus.pending,
        progress=0.0,
        started_at=datetime.now(),
    )
    assert job.status == JobStatus.pending
    assert job.result is None


def test_period_return_model():
    pr = PeriodReturn(
        period="monthly",
        labels=["2026-01", "2026-02"],
        returns=[0.01, 0.02],
        benchmark_returns=[0.005, 0.01],
    )
    assert pr.period == "monthly"
    assert len(pr.returns) == 2


def test_nav_curve_model():
    nc = NavCurve(
        dates=[date(2026, 1, 1)],
        nav=[1.0],
        drawdown=[0.0],
        benchmark_nav=[1.0],
    )
    assert nc.drawdown == [0.0]


def test_paginated_data_generic():
    pd_ = PaginatedData[FundListItem](
        items=[FundListItem(fund_code="000001")], page=1, size=20, total=1
    )
    assert pd_.total == 1
    assert pd_.items[0].fund_code == "000001"


def test_strategy_summary():
    s = StrategySummary(strategy_id="s1", prototype_id="proto_4433", domain="成长")
    assert s.domain == "成长"
    assert s.adopted is False


def test_business_error_defaults():
    err = BusinessError("oops")
    assert err.status_code == 400
    nf = BusinessError("nf", status_code=404)
    assert nf.status_code == 404


def test_error_response_serialization():
    er = ErrorResponse(code=422, message="invalid", detail={"f": ["e"]})
    dumped = er.model_dump()
    assert dumped["detail"]["f"] == ["e"]
