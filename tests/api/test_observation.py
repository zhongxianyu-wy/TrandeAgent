"""observation 路由测试（T07，FR-4）。"""
from __future__ import annotations

from datetime import date

from unittest.mock import MagicMock

from src.api import deps
from src.api.schema import BusinessError


def test_list_observation(client, mock_config_manager):
    # 首次访问从 config 同步（observation_pool=['000001']）
    r = client.get("/api/observation")
    assert r.status_code == 200
    pool = r.json()["data"]["pool"]
    assert "000001" in pool


def test_add_observation(client, mock_feishu_writer):
    r = client.post("/api/observation/161725")
    assert r.status_code == 200
    assert r.json()["data"]["in_pool"] is True
    # 列表中应出现
    r2 = client.get("/api/observation")
    assert "161725" in r2.json()["data"]["pool"]


def test_add_observation_idempotent(client):
    r1 = client.post("/api/observation/000001")
    assert r1.status_code == 200
    r2 = client.post("/api/observation/000001")
    assert r2.status_code == 200
    # 仅一条
    pool = client.get("/api/observation").json()["data"]["pool"]
    assert pool.count("000001") == 1


def test_remove_observation(client):
    client.post("/api/observation/161725")
    r = client.delete("/api/observation/161725")
    assert r.status_code == 200
    assert r.json()["data"]["in_pool"] is False
    pool = client.get("/api/observation").json()["data"]["pool"]
    assert "161725" not in pool


def test_remove_nonexistent(client):
    r = client.delete("/api/observation/999999")
    assert r.status_code == 200
    assert r.json()["data"]["in_pool"] is False


def test_get_signals(client):
    r = client.get("/api/observation/000001/signals")
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) == 1
    assert data[0]["fund_code"] == "000001"


def test_get_signals_engine_unavailable(client, app):
    app.dependency_overrides[deps.get_signal_engine] = lambda: None
    r = client.get("/api/observation/000001/signals")
    assert r.status_code == 400


def test_get_signals_calc_error(client, app, mock_signal_engine):
    mock_signal_engine.calc_signals.side_effect = RuntimeError("err")
    app.dependency_overrides[deps.get_signal_engine] = lambda: mock_signal_engine
    r = client.get("/api/observation/000001/signals")
    assert r.status_code == 400


def test_feishu_sync_called(client, mock_feishu_writer):
    client.post("/api/observation/005827")
    mock_feishu_writer.add_to_pool.assert_called_with("005827")


def test_feishu_sync_failure_swallowed(client, app, mock_feishu_writer):
    """飞书同步失败不应阻断 API。"""
    mock_feishu_writer.add_to_pool.side_effect = RuntimeError("feishu down")
    app.dependency_overrides[deps.get_feishu_writer] = lambda: mock_feishu_writer
    r = client.post("/api/observation/005827")
    assert r.status_code == 200


def test_persist_pool_failure_swallowed(client, app, mock_config_manager):
    """配置持久化失败不应阻断 API。"""
    mock_config_manager.save_with_commit.side_effect = RuntimeError("git err")
    app.dependency_overrides[deps.get_config_manager] = lambda: mock_config_manager
    r = client.post("/api/observation/005827")
    assert r.status_code == 200
