"""配置管理路由（T08，FR-5）。

端点：GET 当前配置 / PUT 更新(含影响范围检测) / 历史版本 / 回滚。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import ValidationError

from src.api.deps import get_config_manager
from src.api.schema import ApiResponse, BusinessError, NotFoundError

router = APIRouter()


@router.get("", summary="当前配置")
def get_config(config_manager=Depends(get_config_manager)) -> ApiResponse:
    """当前配置。"""
    if config_manager is None:
        raise BusinessError("配置管理器不可用")
    try:
        cfg = config_manager.load()  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        raise BusinessError(f"加载配置失败：{exc}") from exc
    return ApiResponse(data=cfg.model_dump(mode="json"))


@router.put("", summary="更新配置（含影响范围检测）")
def update_config(
    payload: dict,
    config_manager=Depends(get_config_manager),
) -> ApiResponse:
    """更新配置，返回 ChangeImpact 列表。"""
    if config_manager is None:
        raise BusinessError("配置管理器不可用")
    try:
        old = config_manager.load()  # type: ignore[attr-defined]
        from src.config_manager.schema import AppConfig

        new = AppConfig(**payload)
    except ValidationError as exc:
        raise BusinessError(
            "配置校验失败", status_code=422, detail={"errors": exc.errors()}
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise BusinessError(f"配置解析失败：{exc}") from exc

    # 影响范围检测
    impacts = config_manager.analyze_impact(old, new)  # type: ignore[attr-defined]
    impact_data = [i.model_dump(mode="json") for i in impacts]

    # 保存 + git commit
    try:
        config_manager.save_with_commit(new, "api: 更新配置")  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        raise BusinessError(f"配置保存失败：{exc}") from exc

    return ApiResponse(
        data={
            "impacts": impact_data,
            "affected_count": sum(
                len(i.get("affected_funds", [])) for i in impact_data
            ),
        }
    )


@router.get("/history", summary="配置版本历史")
def config_history(
    n: int = 10,
    config_manager=Depends(get_config_manager),
) -> ApiResponse:
    """配置版本历史。"""
    if config_manager is None:
        raise BusinessError("配置管理器不可用")
    try:
        # DefaultConfigManager 提供 log()
        history = config_manager.log(n)  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        raise BusinessError(f"获取历史失败：{exc}") from exc
    return ApiResponse(data={"history": history})


@router.post("/rollback/{commit}", summary="回滚配置")
def rollback_config(
    commit: str,
    config_manager=Depends(get_config_manager),
) -> ApiResponse:
    """回滚配置到指定 commit。"""
    if config_manager is None:
        raise BusinessError("配置管理器不可用")
    try:
        cfg = config_manager.rollback(commit)  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        raise NotFoundError(f"回滚失败：{exc}") from exc
    return ApiResponse(data=cfg.model_dump(mode="json"))


__all__ = ["router"]
