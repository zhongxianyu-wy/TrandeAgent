"""discover 路由测试（T06，FR-3）。"""
from __future__ import annotations

from datetime import date

from unittest.mock import MagicMock

from src.api import deps


def test_discover_all_domains(client, mock_engine):
    # engine 返回非空 batch
    import pandas as pd

    mock_engine.calc_batch.return_value = pd.DataFrame(
        [{"fund_code": "000001", "rating": 4, "return_1y": 0.15}]
    )
    r = client.get("/api/discover")
    assert r.status_code == 200
    data = r.json()["data"]
    assert "domains" in data
    assert len(data["domains"]) == 8
    assert data["domains"]["价值"] == ["000001"]


def test_discover_single_domain(client):
    r = client.get("/api/discover?domain=成长")
    assert r.status_code == 200
    data = r.json()["data"]
    assert "成长" in data["domains"]


def test_discover_engine_unavailable(client, app):
    app.dependency_overrides[deps.get_indicator_engine] = lambda: None
    r = client.get("/api/discover")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["domains"]["价值"] == []


def test_discover_reasons(client):
    r = client.get("/api/discover/reasons/000001")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["fund_code"] == "000001"
    assert len(data["reasons"]) >= 1


def test_discover_reasons_engine_unavailable(client, app):
    app.dependency_overrides[deps.get_indicator_engine] = lambda: None
    r = client.get("/api/discover/reasons/000001")
    assert r.status_code == 200
    assert r.json()["data"]["reasons"] == []


def test_discover_reasons_calc_error(client, app, mock_engine):
    mock_engine.calc_all.side_effect = ValueError("boom")
    app.dependency_overrides[deps.get_indicator_engine] = lambda: mock_engine
    r = client.get("/api/discover/reasons/000001")
    assert r.status_code == 400


def test_discover_window_param(client):
    r = client.get("/api/discover?window=week")
    assert r.status_code == 200
    assert r.json()["data"]["window"] == "week"
