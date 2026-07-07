"""config 路由测试（T08，FR-5）。"""
from __future__ import annotations

from src.api import deps
from src.config_manager.schema import ChangeImpact
from tests.api.conftest import make_app_config


def test_get_config(client):
    r = client.get("/api/config")
    assert r.status_code == 200
    data = r.json()["data"]
    assert "000001" in data["observation_pool"]


def test_get_config_unavailable(client, app):
    app.dependency_overrides[deps.get_config_manager] = lambda: None
    r = client.get("/api/config")
    assert r.status_code == 400


def test_update_config_no_impact(client, mock_config_manager):
    payload = make_app_config().model_dump(mode="json")
    r = client.put("/api/config", json=payload)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["affected_count"] == 0
    mock_config_manager.save_with_commit.assert_called_once()


def test_update_config_with_impact(client, mock_config_manager):
    mock_config_manager.analyze_impact.return_value = [
        ChangeImpact(
            change_type="pool",
            added=["161725"],
            affected_funds=["161725"],
            summary="观察池变更",
        )
    ]
    payload = make_app_config(pool=["000001", "161725"]).model_dump(mode="json")
    r = client.put("/api/config", json=payload)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["affected_count"] == 1
    assert data["impacts"][0]["change_type"] == "pool"


def test_update_config_validation_error(client):
    """非法 payload → 422。"""
    r = client.put("/api/config", json={"observation_pool": "not_a_list"})
    assert r.status_code == 422


def test_update_config_save_failure(client, app, mock_config_manager):
    mock_config_manager.save_with_commit.side_effect = RuntimeError("disk full")
    app.dependency_overrides[deps.get_config_manager] = lambda: mock_config_manager
    payload = make_app_config().model_dump(mode="json")
    r = client.put("/api/config", json=payload)
    assert r.status_code == 400


def test_config_history(client):
    r = client.get("/api/config/history")
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data["history"]) == 1


def test_config_rollback(client):
    r = client.post("/api/config/rollback/deadbeef")
    assert r.status_code == 200
    data = r.json()["data"]
    assert "observation_pool" in data


def test_config_rollback_failure(client, app, mock_config_manager):
    mock_config_manager.rollback.side_effect = RuntimeError("bad commit")
    app.dependency_overrides[deps.get_config_manager] = lambda: mock_config_manager
    r = client.post("/api/config/rollback/bad")
    assert r.status_code == 404
