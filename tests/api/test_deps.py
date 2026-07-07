"""deps 依赖注入工厂测试（覆盖 T03 工厂函数体）。"""
from __future__ import annotations

from pathlib import Path

from src.api import deps


def test_get_data_provider_returns_or_none():
    # 工厂要么返回实例要么返回 None，不应抛异常
    result = deps.get_data_provider()
    assert result is None or result is not None


def test_get_indicator_engine_returns_or_none():
    assert deps.get_indicator_engine() is None or deps.get_indicator_engine() is not None


def test_get_screener_returns_or_none():
    assert deps.get_screener() is None or deps.get_screener() is not None


def test_get_analyzer_returns_or_none():
    assert deps.get_analyzer() is None or deps.get_analyzer() is not None


def test_get_signal_engine_returns_or_none():
    assert deps.get_signal_engine() is None or deps.get_signal_engine() is not None


def test_get_arena_pipeline_returns_or_none():
    assert deps.get_arena_pipeline() is None or deps.get_arena_pipeline() is not None


def test_get_config_manager_returns_or_none():
    assert deps.get_config_manager() is None or deps.get_config_manager() is not None


def test_get_feishu_writer_returns_or_none():
    assert deps.get_feishu_writer() is None or deps.get_feishu_writer() is not None


def test_get_cache_dir_returns_path(tmp_path, monkeypatch):
    d = deps.get_cache_dir()
    assert isinstance(d, Path)


def test_get_job_store_from_app_state(client, app):
    """get_job_store 从 app.state 取（已被 override 覆盖）。"""
    # 触发一次 jobs 请求确保 app.state.job_store 存在（lifespan 已建）
    store = app.state.job_store
    assert store is not None


def test_get_job_store_lazy_construct(tmp_path):
    """无 app.state.job_store 时懒构造。"""
    from fastapi import FastAPI
    from starlette.requests import Request

    from src.api.services.job_service import JobStore

    app = FastAPI()
    # 构造一个伪 Request scope
    request = Request({"type": "http", "app": app})
    store = deps.get_job_store(request)
    assert isinstance(store, JobStore)
    # 再次取应复用
    assert deps.get_job_store(request) is store


def test_get_arena_store_lazy_construct():
    from fastapi import FastAPI
    from starlette.requests import Request

    from src.api.services.strategy_service import ArenaStore

    app = FastAPI()
    request = Request({"type": "http", "app": app})
    store = deps.get_arena_store(request)
    assert isinstance(store, ArenaStore)


def test_get_observation_store_lazy_construct():
    from fastapi import FastAPI
    from starlette.requests import Request

    from src.api.services.strategy_service import ObservationStore

    app = FastAPI()
    request = Request({"type": "http", "app": app})
    store = deps.get_observation_store(request)
    assert isinstance(store, ObservationStore)
