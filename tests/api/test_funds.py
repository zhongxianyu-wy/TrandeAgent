"""funds 路由测试（T04，FR-1）。"""
from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd

from src.api import deps
from src.api.services import fund_service
from src.api.schema import BusinessError
from tests.api.conftest import (
    make_fund_basic_df,
    make_fund_indicators,
    make_nav_df,
)


def test_list_funds(client):
    r = client.get("/api/funds")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["total"] == 2
    assert data["items"][0]["fund_code"] in {"000001", "161725"}


def test_list_funds_with_search(client):
    r = client.get("/api/funds?search=华夏")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["fund_name"] == "华夏成长"


def test_list_funds_pagination(client):
    r = client.get("/api/funds?page=1&size=1")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["size"] == 1
    assert len(data["items"]) == 1
    assert data["total"] == 2


def test_get_fund_detail(client):
    r = client.get("/api/funds/000001")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["fund_code"] == "000001"
    assert "indicators" in data
    assert data["indicators"]["rating"] == 4


def test_get_fund_detail_not_found(client, app, mock_provider):
    mock_provider.list_funds.return_value = pd.DataFrame()
    app.dependency_overrides[deps.get_data_provider] = lambda: mock_provider
    r = client.get("/api/funds/UNKNOWN")
    assert r.status_code == 404


def test_get_fund_nav(client):
    r = client.get("/api/funds/000001/nav?page=1&size=10")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["total"] == 30
    assert len(data["items"]) == 10


def test_get_fund_nav_date_range(client):
    r = client.get(
        "/api/funds/000001/nav?start=2026-01-01&end=2026-01-15&size=250"
    )
    assert r.status_code == 200


def test_get_fund_report(client):
    r = client.get("/api/funds/000001/report")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["fund_code"] == "000001"
    assert data["label"] == "建议"


def test_get_fund_report_analyzer_unavailable(client, app):
    app.dependency_overrides[deps.get_analyzer] = lambda: None
    r = client.get("/api/funds/000001/report")
    assert r.status_code == 400


def test_analyze_fund_async(client):
    r = client.post("/api/funds/000001/analyze")
    assert r.status_code == 200
    job_id = r.json()["data"]["job_id"]
    assert job_id
    # 后台任务执行后任务应完成
    r2 = client.get(f"/api/jobs/{job_id}")
    assert r2.status_code == 200
    assert r2.json()["data"]["status"] == "succeeded"


def test_get_holdings(client):
    r = client.get("/api/funds/000001/holdings")
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) == 1
    assert data[0]["stock_code"] == "600519"


def test_get_cashflow(client):
    r = client.get("/api/funds/000001/cashflow")
    assert r.status_code == 200
    data = r.json()["data"]
    assert "share_change_yoy" in data


def test_get_cashflow_without_engine():
    """engine 为 None 时退化为经理表。"""
    provider = MagicMock()
    provider.get_manager.return_value = pd.DataFrame(
        [{"manager_name": "张三"}]
    )
    data = fund_service.get_cashflow(provider, "000001", engine=None)
    assert "managers" in data


def test_list_funds_provider_unavailable():
    """provider 缺失 list_funds 方法 → BusinessError。"""
    provider = object()  # 无 list_funds 属性
    try:
        fund_service.list_funds(provider)
        assert False, "应抛 BusinessError"
    except BusinessError as e:
        assert e.status_code == 400
