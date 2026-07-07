"""system 路由测试（T10，FR-7）。"""
from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd

from src.api import deps


def test_health(client):
    r = client.get("/api/system/health")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["status"] == "ok"
    assert data["version"] == "1.0"


def test_system_status(client):
    r = client.get("/api/system/status")
    assert r.status_code == 200
    data = r.json()["data"]
    assert "data_freshness" in data
    assert data["active_jobs"] == 0
    assert data["observation_pool_size"] == 1
    assert data["strategy_count"] == 2


def test_system_status_freshness(client, mock_provider):
    mock_provider.get_freshness_report.return_value = pd.DataFrame(
        [{"fund_code": "000001", "is_stale": 0}]
    )
    r = client.get("/api/system/status")
    data = r.json()["data"]
    assert data["data_freshness"]["total"] == 1


def test_system_status_provider_unavailable(client, app):
    app.dependency_overrides[deps.get_data_provider] = lambda: None
    r = client.get("/api/system/status")
    assert r.status_code == 200
    assert r.json()["data"]["data_freshness"] == {}


def test_system_status_config_load_fallback(client, app, mock_config_manager):
    """config 加载失败时退化为 obs_store.pool 长度。"""
    mock_config_manager.load.side_effect = RuntimeError("cfg err")
    app.dependency_overrides[deps.get_config_manager] = lambda: mock_config_manager
    # obs_store 初始未同步 → pool 为空
    r = client.get("/api/system/status")
    assert r.status_code == 200
