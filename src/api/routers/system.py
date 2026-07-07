"""系统路由（T10，FR-7）。

端点：status（数据新鲜度/上次运行/活跃任务）/ health（健康检查）。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.deps import (
    get_arena_store,
    get_config_manager,
    get_data_provider,
    get_job_store,
    get_observation_store,
)
from src.api.schema import ApiResponse, HealthStatus, SystemStatus

router = APIRouter()


@router.get("/status", summary="系统状态")
def system_status(
    provider=Depends(get_data_provider),
    job_store=Depends(get_job_store),
    config_manager=Depends(get_config_manager),
    obs_store=Depends(get_observation_store),
    arena_store=Depends(get_arena_store),
) -> ApiResponse:
    """系统状态（数据新鲜度/上次运行/活跃任务）。"""
    freshness: dict = {}
    if provider is not None and hasattr(provider, "get_freshness_report"):
        try:
            df = provider.get_freshness_report()
            if df is not None and not df.empty:
                freshness = {
                    "total": int(len(df)),
                    "stale": int(df["is_stale"].sum()) if "is_stale" in df.columns else 0,
                }
        except Exception:  # noqa: BLE001
            freshness = {}

    # 观察池大小
    pool_size = 0
    if config_manager is not None:
        try:
            cfg = config_manager.load()
            pool_size = len(getattr(cfg, "observation_pool", []) or [])
        except Exception:  # noqa: BLE001
            pool_size = len(obs_store.pool)

    status = SystemStatus(
        data_freshness=freshness,
        last_run=arena_store.last_run,
        active_jobs=job_store.count_active(),
        observation_pool_size=pool_size,
        strategy_count=len(arena_store.strategies),
    )
    return ApiResponse(data=status.model_dump(mode="json"))


@router.get("/health", summary="健康检查")
def health() -> ApiResponse:
    """健康检查。"""
    return ApiResponse(data=HealthStatus(status="ok", version="1.0").model_dump())


__all__ = ["router"]
