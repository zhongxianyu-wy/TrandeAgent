"""API 层 Pydantic schema 与统一异常（T02 / T12）。

对应 plan §2 数据模型。所有响应统一用 :class:`ApiResponse` 包装；
错误统一用 :class:`ErrorResponse`。业务异常 :class:`BusinessError` /
:class:`NotFoundError` 由 app.py 注册的全局处理器捕获后转成 ErrorResponse。

注意：API 层不重复实现业务逻辑，仅做协议转换 + 校验。可直接复用业务模块的
Pydantic 模型（如 FundIndicators / FundReport）作为响应体的 data 类型。
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# ---------------------------------------------------------------------------
# 统一响应包装
# ---------------------------------------------------------------------------
class ApiResponse(BaseModel, Generic[T]):
    """统一成功响应包装。"""

    code: int = 0
    message: str = "ok"
    data: Optional[T] = None


class ErrorResponse(BaseModel):
    """统一错误响应。"""

    code: int
    message: str
    detail: Optional[dict[str, Any]] = None


# ---------------------------------------------------------------------------
# 分页
# ---------------------------------------------------------------------------
class PaginatedData(BaseModel, Generic[T]):
    """分页数据包装。"""

    items: list[T] = Field(default_factory=list)
    page: int = 1
    size: int = 20
    total: int = 0


# ---------------------------------------------------------------------------
# 任务（in-memory + SQLite 持久化）
# ---------------------------------------------------------------------------
class JobStatus(str, Enum):
    """任务状态四态。"""

    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class Job(BaseModel):
    """单条任务记录。"""

    job_id: str
    type: str  # refresh-data | backtest | analyze | regenerate
    status: JobStatus
    progress: float = 0.0  # 0-1
    started_at: datetime
    finished_at: Optional[datetime] = None
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# 周期分析 / 净值曲线
# ---------------------------------------------------------------------------
class PeriodReturn(BaseModel):
    """周期收益率序列（多周期柱状图数据）。"""

    period: str  # daily|weekly|monthly|quarterly|yearly
    labels: list[str] = Field(default_factory=list)
    returns: list[float] = Field(default_factory=list)
    benchmark_returns: list[float] = Field(default_factory=list)


class NavCurve(BaseModel):
    """净值曲线 + 回撤 + 基准对比。"""

    dates: list[date] = Field(default_factory=list)
    nav: list[float] = Field(default_factory=list)
    drawdown: list[float] = Field(default_factory=list)  # 负数
    benchmark_nav: list[float] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 业务实体（薄封装，便于 OpenAPI 生成 TS 类型）
# ---------------------------------------------------------------------------
class FundBasicInfo(BaseModel):
    """基金基本信息（来自 fund_basic 表）。"""

    fund_code: str
    fund_name: str = ""
    fund_type: str = ""
    fund_category: str = ""
    manager_names: str = ""
    establish_date: str = ""
    latest_scale: Optional[float] = None
    management_fee: Optional[float] = None
    custodian_fee: Optional[float] = None
    history_months: Optional[int] = None


class FundListItem(BaseModel):
    """基金列表项（含评级与近 1 年收益，便于前端排序）。"""

    fund_code: str
    fund_name: str = ""
    fund_category: str = ""
    fund_type: str = ""
    latest_scale: Optional[float] = None
    rating: int = 0
    return_1y: Optional[float] = None


class NavPoint(BaseModel):
    """单条净值。"""

    trade_date: date
    unit_nav: Optional[float] = None
    accum_nav: Optional[float] = None
    daily_return: Optional[float] = None


class StrategySummary(BaseModel):
    """策略摘要（列表用）。"""

    strategy_id: str
    prototype_id: str
    domain: str
    rank_in_domain: Optional[int] = None
    composite_score: Optional[float] = None
    annual_return: Optional[float] = None
    sharpe: Optional[float] = None
    max_drawdown: Optional[float] = None
    adopted: bool = False
    disabled: bool = False


class SystemStatus(BaseModel):
    """系统状态。"""

    data_freshness: dict[str, Any] = Field(default_factory=dict)
    last_run: Optional[str] = None
    active_jobs: int = 0
    observation_pool_size: int = 0
    strategy_count: int = 0


class HealthStatus(BaseModel):
    """健康检查。"""

    status: str = "ok"
    version: str = "1.0"


# ---------------------------------------------------------------------------
# 统一业务异常（T12）
# ---------------------------------------------------------------------------
class BusinessError(Exception):
    """业务异常基类，默认 400。

    Attributes:
        status_code: HTTP 状态码。
        message: 错误消息。
        detail: 附加详情（放入 ErrorResponse.detail）。
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 400,
        detail: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.detail = detail


class NotFoundError(BusinessError):
    """资源不存在（404）。"""

    def __init__(self, message: str, detail: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message, status_code=404, detail=detail)


__all__ = [
    "ApiResponse",
    "ErrorResponse",
    "PaginatedData",
    "JobStatus",
    "Job",
    "PeriodReturn",
    "NavCurve",
    "NavPoint",
    "FundBasicInfo",
    "FundListItem",
    "StrategySummary",
    "SystemStatus",
    "HealthStatus",
    "BusinessError",
    "NotFoundError",
]
