"""策略竞技场路由（T05，FR-2）。

端点：列表 / 详情 / 周期分析 / 净值曲线 / 现金流 / 采用 / 停用 / 重新生成(异步)。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query

from src.api.deps import (
    get_arena_pipeline,
    get_arena_store,
    get_job_store,
)
from src.api.schema import ApiResponse, PaginatedData
from src.api.services import strategy_service

router = APIRouter()


@router.get("", summary="策略列表")
def list_strategies(
    domain: Optional[str] = Query(None, description="领域过滤"),
    sort: str = Query("score", description="排序：score|return|sharpe|drawdown"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    store=Depends(get_arena_store),
) -> ApiResponse[PaginatedData]:
    """策略列表（按领域分组 + 排名）。"""
    data = strategy_service.list_strategies(
        store, domain=domain, sort=sort, page=page, size=size
    )
    return ApiResponse(data=data)


@router.get("/{strategy_id}", summary="策略详情")
def get_strategy(
    strategy_id: str, store=Depends(get_arena_store)
) -> ApiResponse:
    """策略详情（含来源/参数/回测结果）。"""
    data = strategy_service.get_strategy(store, strategy_id)
    return ApiResponse(data=data)


@router.get("/{strategy_id}/timeseries", summary="周期分析数据")
def get_strategy_timeseries(
    strategy_id: str,
    period: str = Query("monthly", description="daily|weekly|monthly|quarterly|yearly"),
    store=Depends(get_arena_store),
) -> ApiResponse:
    """策略周期分析数据（多周期收益柱状图）。"""
    data = strategy_service.get_strategy_timeseries(store, strategy_id, period=period)
    return ApiResponse(data=data)


@router.get("/{strategy_id}/nav", summary="净值曲线")
def get_strategy_nav(
    strategy_id: str,
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    benchmark: Optional[str] = Query(None),
    store=Depends(get_arena_store),
) -> ApiResponse:
    """净值曲线 + 回撤 + 基准对比。"""
    del start, end  # 周期内全量返回；预留参数兼容前端
    data = strategy_service.get_strategy_nav(store, strategy_id, benchmark=benchmark)
    return ApiResponse(data=data)


@router.get("/{strategy_id}/cashflow", summary="现金流时序")
def get_strategy_cashflow(
    strategy_id: str, store=Depends(get_arena_store)
) -> ApiResponse:
    """策略现金流时序。"""
    data = strategy_service.get_strategy_cashflow(store, strategy_id)
    return ApiResponse(data=data)


@router.post("/{strategy_id}/adopt", summary="采用策略")
def adopt_strategy(
    strategy_id: str,
    store=Depends(get_arena_store),
) -> ApiResponse:
    """采用策略 → 写入观察池。"""
    data = strategy_service.adopt_strategy(store, strategy_id)
    return ApiResponse(data=data)


@router.post("/{strategy_id}/disable", summary="停用策略")
def disable_strategy(
    strategy_id: str, store=Depends(get_arena_store)
) -> ApiResponse:
    """停用策略。"""
    data = strategy_service.disable_strategy(store, strategy_id)
    return ApiResponse(data=data)


@router.post("/regenerate", summary="重新生成策略")
def regenerate_strategies(
    background_tasks: BackgroundTasks,
    count: int = Query(50, ge=1, le=500),
    arena_pipeline=Depends(get_arena_pipeline),
    store=Depends(get_arena_store),
    job_store=Depends(get_job_store),
) -> ApiResponse:
    """重新生成策略（异步任务）。"""
    from src.api.services import job_service

    job = job_store.create_job("regenerate")
    background_tasks.add_task(
        job_service.run_regenerate, job_store, job.job_id, arena_pipeline, count
    )
    return ApiResponse(data={"job_id": job.job_id})


__all__ = ["router"]
