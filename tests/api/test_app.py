"""应用级测试（T01 / T12）。"""
from __future__ import annotations

from fastapi.testclient import TestClient

from src.api import deps
from src.api.app import app, create_app
from src.api.schema import BusinessError, ErrorResponse, NotFoundError


def test_app_routes_registered():
    """7 个路由组前缀全部注册（通过 OpenAPI schema 校验）。"""
    schema = app.openapi()
    paths = set(schema["paths"].keys())
    prefixes = [
        "/api/funds",
        "/api/strategies",
        "/api/discover",
        "/api/observation",
        "/api/config",
        "/api/jobs",
        "/api/system",
    ]
    for pre in prefixes:
        assert any(p.startswith(pre) for p in paths), f"缺少路由前缀 {pre}"


def test_openapi_schema_available(client):
    """OpenAPI schema 可生成。"""
    r = client.get("/openapi.json")
    assert r.status_code == 200
    schema = r.json()
    assert schema["info"]["title"] == "TrandeAgent API"
    assert "/api/funds" in schema["paths"] or "/api/funds/" in schema["paths"]


def test_cors_header(client):
    """CORS 允许 localhost:3000。"""
    r = client.options(
        "/api/system/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    # 预检请求应返回 200 并带 CORS 头
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_business_error_to_jsonresponse(client, app, mock_provider):
    """BusinessError → ErrorResponse（400）。"""
    mock_provider.list_funds.side_effect = BusinessError("模拟业务错误")
    app.dependency_overrides[deps.get_data_provider] = lambda: mock_provider
    r = client.get("/api/funds")
    assert r.status_code == 400
    body = r.json()
    assert body["code"] == 400
    assert "模拟业务错误" in body["message"]


def test_not_found_error(client, app, mock_provider):
    """NotFoundError → 404。"""
    mock_provider.list_funds.return_value = __import__("pandas").DataFrame()
    from unittest.mock import MagicMock

    engine = MagicMock()
    engine.calc_batch.return_value = __import__("pandas").DataFrame()
    app.dependency_overrides[deps.get_data_provider] = lambda: mock_provider
    app.dependency_overrides[deps.get_indicator_engine] = lambda: engine
    r = client.get("/api/funds/UNKNOWN")
    assert r.status_code == 404


def test_unhandled_exception_to_500(client, app, mock_provider):
    """未处理异常 → 500 ErrorResponse。"""
    mock_provider.list_funds.side_effect = RuntimeError("boom")
    app.dependency_overrides[deps.get_data_provider] = lambda: mock_provider
    r = client.get("/api/funds")
    assert r.status_code == 500
    assert r.json()["code"] == 500


def test_request_validation_error_422(client):
    """请求参数校验失败 → 422。"""
    # page 必须 >=1，传 0 触发校验失败
    r = client.get("/api/funds?page=0")
    assert r.status_code == 422
    body = r.json()
    assert body["code"] == 422


def test_create_app_idempotent():
    """create_app 可重复构造。"""
    a = create_app()
    assert a.title == "TrandeAgent API"


def test_exception_models():
    """异常类携带 status_code/detail。"""
    err = BusinessError("x", detail={"k": "v"})
    assert err.status_code == 400
    assert err.detail == {"k": "v"}
    nf = NotFoundError("missing")
    assert nf.status_code == 404


def test_error_response_model():
    er = ErrorResponse(code=400, message="bad", detail=None)
    assert er.code == 400
    assert er.message == "bad"
