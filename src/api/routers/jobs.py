"""任务管理路由（T09，FR-6）。

端点：refresh-data / backtest / analyze(批量) / 查询任务状态 / 列表。
所有触发类端点创建 pending Job 后用 BackgroundTasks 执行业务函数。
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from pydantic import BaseModel

from src.api.deps import (
    get_analyzer,
    get_arena_pipeline,
    get_data_provider,
    get_job_store,
)
from src.api.schema import ApiResponse, JobStatus, NotFoundError

router = APIRouter()


class RefreshDataRequest(BaseModel):
    fund_codes: Optional[List[str]] = None


class BacktestRequest(BaseModel):
    count: int = 50


class AnalyzeRequest(BaseModel):
    fund_codes: List[str]


@router.post("/refresh-data", summary="触发数据刷新")
def refresh_data(
    background_tasks: BackgroundTasks,
    req: Optional[RefreshDataRequest] = None,
    provider=Depends(get_data_provider),
    job_store=Depends(get_job_store),
) -> ApiResponse:
    """触发数据刷新（来自 #1）。"""
    from src.api.services import job_service

    job = job_store.create_job("refresh-data")
    # 包装一个闭包，忽略 fund_codes 参数透传
    background_tasks.add_task(
        job_service.run_refresh_data, job_store, job.job_id, provider
    )
    return ApiResponse(data={"job_id": job.job_id})


@router.post("/backtest", summary="触发回测")
def backtest(
    background_tasks: BackgroundTasks,
    req: Optional[BacktestRequest] = None,
    arena_pipeline=Depends(get_arena_pipeline),
    job_store=Depends(get_job_store),
) -> ApiResponse:
    """触发策略回测（来自 #8）。"""
    from src.api.services import job_service

    count = req.count if req else 50
    job = job_store.create_job("backtest")
    background_tasks.add_task(
        job_service.run_backtest, job_store, job.job_id, arena_pipeline, count
    )
    return ApiResponse(data={"job_id": job.job_id})


@router.post("/analyze", summary="触发批量分析")
def analyze(
    background_tasks: BackgroundTasks,
    req: AnalyzeRequest,
    analyzer=Depends(get_analyzer),
    job_store=Depends(get_job_store),
) -> ApiResponse:
    """触发批量分析（来自 #6）。"""
    from src.api.services import job_service

    job = job_store.create_job("analyze")
    background_tasks.add_task(
        job_service.run_batch_analyze,
        job_store,
        job.job_id,
        analyzer,
        list(req.fund_codes),
    )
    return ApiResponse(data={"job_id": job.job_id})


@router.get("/{job_id}", summary="任务状态查询")
def get_job(
    job_id: str, job_store=Depends(get_job_store)
) -> ApiResponse:
    """任务状态查询（status/progress/result）。"""
    job = job_store.get_job(job_id)
    if job is None:
        raise NotFoundError(f"任务 {job_id} 不存在")
    return ApiResponse(data=job.model_dump(mode="json"))


@router.get("", summary="任务列表")
def list_jobs(
    status: Optional[JobStatus] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    job_store=Depends(get_job_store),
) -> ApiResponse:
    """任务列表。"""
    jobs = job_store.list_jobs(status=status, limit=limit)
    return ApiResponse(data={"items": [j.model_dump(mode="json") for j in jobs]})


__all__ = ["router"]
