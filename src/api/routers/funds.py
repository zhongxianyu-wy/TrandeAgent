"""基金路由（T04，FR-1）。

7 个端点：列表 / 详情 / 净值 / 报告 / 分析(异步) / 持仓 / 现金流。
只做协议转换，业务逻辑由 fund_service + 业务模块完成。
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query

from src.api.services import fund_service
from src.api.deps import (
    get_analyzer,
    get_data_provider,
    get_indicator_engine,
    get_job_store,
)
from src.api.schema import ApiResponse, PaginatedData

router = APIRouter()


@router.get("", summary="基金列表")
def list_funds(
    category: Optional[str] = Query(None, description="大类过滤"),
    domain: Optional[str] = Query(None, description="领域过滤"),
    search: Optional[str] = Query(None, description="名称/代码模糊搜索"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    provider=Depends(get_data_provider),
    engine=Depends(get_indicator_engine),
) -> ApiResponse[PaginatedData]:
    """基金列表（支持分类/领域/搜索 + 分页）。"""
    data = fund_service.list_funds(
        provider,
        category=category,
        domain=domain,
        search=search,
        page=page,
        size=size,
        engine=engine,
    )
    return ApiResponse(data=data)


@router.get("/{code}", summary="单基金详情")
def get_fund(
    code: str,
    provider=Depends(get_data_provider),
    engine=Depends(get_indicator_engine),
) -> ApiResponse:
    """单基金详情（含 L1-L4 指标）。"""
    data = fund_service.get_fund_detail(provider, engine, code)
    return ApiResponse(data=data)


@router.get("/{code}/nav", summary="净值序列")
def get_fund_nav(
    code: str,
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(250, ge=1, le=1000),
    provider=Depends(get_data_provider),
) -> ApiResponse[PaginatedData]:
    """净值序列（分页，默认 250 天/页）。"""
    data = fund_service.get_nav(
        provider, code, start=start, end=end, page=page, size=size
    )
    return ApiResponse(data=data)


@router.get("/{code}/report", summary="LLM 分析报告")
def get_fund_report(
    code: str, analyzer=Depends(get_analyzer)
) -> ApiResponse:
    """单基金 LLM 报告（来自分析器缓存或实时计算）。"""
    data = fund_service.get_report(analyzer, code)
    return ApiResponse(data=data)


@router.post("/{code}/analyze", summary="触发 AI 重新分析")
def analyze_fund(
    code: str,
    background_tasks: BackgroundTasks,
    analyzer=Depends(get_analyzer),
    job_store=Depends(get_job_store),
) -> ApiResponse:
    """触发 AI 重新分析（异步任务），返回 job_id。"""
    from src.api.services import job_service

    job = job_store.create_job("analyze")
    background_tasks.add_task(
        job_service.run_analyze, job_store, job.job_id, analyzer, code
    )
    return ApiResponse(data={"job_id": job.job_id})


@router.get("/{code}/holdings", summary="持仓明细")
def get_fund_holdings(
    code: str, provider=Depends(get_data_provider)
) -> ApiResponse:
    """持仓明细。"""
    data = fund_service.get_holdings(provider, code)
    return ApiResponse(data=data)


@router.get("/{code}/cashflow", summary="现金流")
def get_fund_cashflow(
    code: str,
    provider=Depends(get_data_provider),
    engine=Depends(get_indicator_engine),
) -> ApiResponse:
    """现金流（份额变动/机构持有）。"""
    data = fund_service.get_cashflow(provider, code, engine)
    return ApiResponse(data=data)


__all__ = ["router"]
