"""依赖注入（T03）。

业务模块单例通过 lru_cache 缓存，保证整个进程只构造一次。
真实部署时工厂会构造各业务模块的默认实现；构造失败则返回 None（路由层应
在测试中通过 ``dependency_overrides`` 注入 mock，真实无基础设施时返回 500）。

任务存储 :class:`JobStore` 不走 lru_cache：它需要随应用生命周期管理 SQLite
连接，存放在 ``app.state`` 上，由 :func:`get_job_store` 从 request 上下文取回。

观测池 / 策略竞技场的运行态同样存放在 ``app.state``（进程内单例）。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from fastapi import Request

# 项目根（用于定位 config / data 目录）
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_CONFIG_DIR = _PROJECT_ROOT / "config"
_DEFAULT_CACHE_DIR = _PROJECT_ROOT / "data" / "cache"


# ---------------------------------------------------------------------------
# 业务模块单例（lru_cache）
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_data_provider() -> Any:
    """返回 DataProvider 单例（AkShareProvider）。构造失败返回 None。"""
    try:  # 延迟 import，避免 app 导入时触发重依赖
        from src.data.akshare_provider import AkShareProvider
        from src.data.config import load_data_config

        config = load_data_config()
        config.ensure_dirs()
        return AkShareProvider(config)
    except Exception:  # noqa: BLE001
        return None


@lru_cache(maxsize=1)
def get_indicator_engine() -> Any:
    """返回 IndicatorEngine 单例。"""
    provider = get_data_provider()
    if provider is None:
        return None
    try:
        from src.indicators.default_engine import DefaultIndicatorEngine

        return DefaultIndicatorEngine(provider)
    except Exception:  # noqa: BLE001
        return None


@lru_cache(maxsize=1)
def get_screener() -> Any:
    """返回 ScreenerEngine 单例。"""
    try:
        from src.screener.engine import DefaultScreener

        return DefaultScreener()
    except Exception:  # noqa: BLE001
        return None


@lru_cache(maxsize=1)
def get_analyzer() -> Any:
    """返回 FundAnalyzer 单例（需 LLM client，缺失时返回 None）。"""
    engine = get_indicator_engine()
    if engine is None:
        return None
    try:
        from src.analyzer.analyzer import DefaultAnalyzer
        from src.analyzer.llm.client import LLMClient

        return DefaultAnalyzer(engine, LLMClient())  # type: ignore[arg-type]
    except Exception:  # noqa: BLE001
        return None


@lru_cache(maxsize=1)
def get_signal_engine() -> Any:
    """返回 SignalEngine 单例。"""
    provider = get_data_provider()
    if provider is None:
        return None
    try:
        from src.signal.engine import DefaultSignalEngine

        return DefaultSignalEngine(provider)
    except Exception:  # noqa: BLE001
        return None


@lru_cache(maxsize=1)
def get_arena_pipeline() -> Any:
    """返回 ArenaPipeline 单例（需要 nav 序列 + LLM，缺失返回 None）。"""
    try:
        import pandas as pd

        from src.arena.pipeline import make_default_pipeline

        nav = pd.Series(dtype=float)
        return make_default_pipeline(nav, llm_client=None)
    except Exception:  # noqa: BLE001
        return None


@lru_cache(maxsize=1)
def get_config_manager() -> Any:
    """返回 ConfigManager 单例（绑定默认策略配置文件）。"""
    try:
        from src.config_manager.manager import DefaultConfigManager

        # 优先用聚合配置文件，缺失则退到 screener.yaml
        target = _DEFAULT_CONFIG_DIR / "strategy.yaml"
        if not target.exists():
            target = _DEFAULT_CONFIG_DIR / "screener.yaml"
        return DefaultConfigManager(target)
    except Exception:  # noqa: BLE001
        return None


@lru_cache(maxsize=1)
def get_feishu_writer() -> Any:
    """返回飞书 Base 写入器单例（可选）。缺失返回 None。"""
    try:
        from src.feishu.lark_cli_client import LarkCliClient  # type: ignore

        return LarkCliClient()
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# 进程内运行态（存于 app.state，非 lru_cache）
# ---------------------------------------------------------------------------
def get_job_store(request: Request) -> "JobStore":  # type: ignore[name-defined]
    """从 app.state 取 JobStore（lifespan 中初始化）。"""
    store = getattr(request.app.state, "job_store", None)
    if store is None:  # 兜底：测试或未走 lifespan 时懒构造
        from src.api.services.job_service import JobStore

        store = JobStore()
        request.app.state.job_store = store
    return store


def get_arena_store(request: Request) -> "ArenaStore":  # type: ignore[name-defined]
    """从 app.state 取竞技场运行态存储。"""
    store = getattr(request.app.state, "arena_store", None)
    if store is None:
        from src.api.services.strategy_service import ArenaStore

        store = ArenaStore()
        request.app.state.arena_store = store
    return store


def get_observation_store(request: Request) -> "ObservationStore":  # type: ignore[name-defined]
    """从 app.state 取观察池运行态存储。"""
    store = getattr(request.app.state, "observation_store", None)
    if store is None:
        from src.api.services.strategy_service import ObservationStore

        store = ObservationStore()
        request.app.state.observation_store = store
    return store


def get_cache_dir() -> Path:
    """返回默认缓存目录（供 JobStore SQLite 使用）。"""
    _DEFAULT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _DEFAULT_CACHE_DIR


__all__ = [
    "get_data_provider",
    "get_indicator_engine",
    "get_screener",
    "get_analyzer",
    "get_signal_engine",
    "get_arena_pipeline",
    "get_config_manager",
    "get_feishu_writer",
    "get_job_store",
    "get_arena_store",
    "get_observation_store",
    "get_cache_dir",
]
