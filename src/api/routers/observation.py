"""观察池路由（T07，FR-4）。

端点：列表 / 加入(同步飞书 Base) / 移出 / 信号。
观察池以 ConfigManager 持久化为准，ObservationStore 作内存镜像。
加入/移出时同步写飞书 Base（可选，失败仅告警不阻断）。
"""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends

from src.api.deps import (
    get_config_manager,
    get_feishu_writer,
    get_observation_store,
    get_signal_engine,
)
from src.api.schema import ApiResponse, BusinessError, NotFoundError

router = APIRouter()


def _ensure_synced(obs_store, config_manager) -> None:
    """首次访问时从配置同步观察池。"""
    if not obs_store.initialized:
        obs_store.sync_from_config(config_manager)


def _persist_pool(obs_store, config_manager) -> None:
    """把内存池写回配置（save_with_commit）。"""
    if config_manager is None:
        return
    try:
        cfg = config_manager.load()  # type: ignore[attr-defined]
        cfg.observation_pool = list(obs_store.pool)
        config_manager.save_with_commit(cfg, "api: 更新观察池")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        # 配置持久化失败不阻断 API（本地仍生效）
        pass


@router.get("", summary="观察池列表")
def list_observation(
    config_manager=Depends(get_config_manager),
    obs_store=Depends(get_observation_store),
) -> ApiResponse:
    """观察池列表。"""
    _ensure_synced(obs_store, config_manager)
    return ApiResponse(data={"pool": list(obs_store.pool)})


@router.post("/{code}", summary="加入观察池")
def add_observation(
    code: str,
    config_manager=Depends(get_config_manager),
    obs_store=Depends(get_observation_store),
    feishu_writer=Depends(get_feishu_writer),
) -> ApiResponse:
    """加入观察池（同时写本地 + 飞书 Base）。"""
    _ensure_synced(obs_store, config_manager)
    if code not in obs_store.pool:
        obs_store.pool.append(code)
        _persist_pool(obs_store, config_manager)
        _sync_feishu_add(feishu_writer, code)
    return ApiResponse(data={"code": code, "in_pool": True})


@router.delete("/{code}", summary="移出观察池")
def remove_observation(
    code: str,
    config_manager=Depends(get_config_manager),
    obs_store=Depends(get_observation_store),
    feishu_writer=Depends(get_feishu_writer),
) -> ApiResponse:
    """移出观察池。"""
    _ensure_synced(obs_store, config_manager)
    if code in obs_store.pool:
        obs_store.pool.remove(code)
        _persist_pool(obs_store, config_manager)
        _sync_feishu_remove(feishu_writer, code)
    return ApiResponse(data={"code": code, "in_pool": False})


@router.get("/{code}/signals", summary="历史信号")
def get_signals(
    code: str,
    signal_engine=Depends(get_signal_engine),
    config_manager=Depends(get_config_manager),
    obs_store=Depends(get_observation_store),
) -> ApiResponse:
    """该基金历史信号。"""
    if signal_engine is None:
        raise BusinessError("信号引擎不可用")
    _ensure_synced(obs_store, config_manager)
    rules = _load_signal_rules(config_manager)
    try:
        signals = signal_engine.calc_signals([code], rules)  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        raise BusinessError(f"信号计算失败：{exc}") from exc
    data = [s.model_dump(mode="json") for s in signals]
    return ApiResponse(data=data)


# ---------------------------------------------------------------------------
# 飞书 Base 同步（可选，失败仅告警）
# ---------------------------------------------------------------------------
def _sync_feishu_add(feishu_writer: Any, code: str) -> None:
    if feishu_writer is None:
        return
    try:
        if hasattr(feishu_writer, "add_to_pool"):
            feishu_writer.add_to_pool(code)
    except Exception:  # noqa: BLE001
        pass


def _sync_feishu_remove(feishu_writer: Any, code: str) -> None:
    if feishu_writer is None:
        return
    try:
        if hasattr(feishu_writer, "remove_from_pool"):
            feishu_writer.remove_from_pool(code)
    except Exception:  # noqa: BLE001
        pass


def _load_signal_rules(config_manager: Any) -> list:
    """从配置加载信号规则（失败返回空列表）。"""
    if config_manager is None:
        return []
    try:
        cfg = config_manager.load()  # type: ignore[attr-defined]
        return list(getattr(cfg, "signal_rules", []) or [])
    except Exception:  # noqa: BLE001
        return []


__all__ = ["router"]
