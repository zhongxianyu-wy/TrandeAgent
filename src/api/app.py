"""FastAPI 应用骨架 + 路由注册 + CORS + 统一错误处理（T01 / T12）。

核心原则：API 层不重复实现业务逻辑，只做协议转换 + Pydantic schema 校验。
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from src.api.deps import get_cache_dir
from src.api.schema import BusinessError, ErrorResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化 JobStore SQLite；关闭时清理连接。"""
    from src.api.services.job_service import JobStore

    db_path = get_cache_dir() / "api_jobs.db"
    app.state.job_store = JobStore(db_path)
    try:
        yield
    finally:
        store = getattr(app.state, "job_store", None)
        if store is not None:
            store.close()


def create_app() -> FastAPI:
    """构造 FastAPI 应用（便于测试注入 lifespan 状态）。"""
    app = FastAPI(
        title="TrandeAgent API",
        version="1.0",
        description="基金投资助手本地后端 API（Feature #11）",
        lifespan=lifespan,
    )

    # CORS：允许前端 localhost:3000
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册 7 个路由组
    from src.api.routers import (
        config,
        discover,
        funds,
        jobs,
        observation,
        strategies,
        system,
    )

    app.include_router(funds.router, prefix="/api/funds", tags=["funds"])
    app.include_router(
        strategies.router, prefix="/api/strategies", tags=["strategies"]
    )
    app.include_router(discover.router, prefix="/api/discover", tags=["discover"])
    app.include_router(
        observation.router, prefix="/api/observation", tags=["observation"]
    )
    app.include_router(config.router, prefix="/api/config", tags=["config"])
    app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
    app.include_router(system.router, prefix="/api/system", tags=["system"])

    _register_exception_handlers(app)
    return app


def _register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器（T12 统一错误响应）。"""

    @app.exception_handler(BusinessError)
    async def business_error_handler(request: Request, exc: BusinessError):
        del request
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                code=exc.status_code, message=exc.message, detail=exc.detail
            ).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ):
        del request
        # Pydantic 校验失败 → 422
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                code=422,
                message="请求参数校验失败",
                detail={"errors": exc.errors()},
            ).model_dump(),
        )

    @app.exception_handler(ValidationError)
    async def pydantic_validation_handler(
        request: Request, exc: ValidationError
    ):
        del request
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                code=422,
                message="数据校验失败",
                detail={"errors": exc.errors()},
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        del request
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                code=500, message="服务器内部错误", detail={"error": str(exc)}
            ).model_dump(),
        )


# 模块级 app（供 uvicorn / openapi 引用）
app = create_app()


__all__ = ["app", "create_app"]
