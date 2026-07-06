# Feature #11 — api-backend 实施计划

> 含 5 要素

---

## 1. 技术选型

| 库 | 版本 | 用途 |
|---|---|---|
| `fastapi` | ≥0.111 | Web 框架 |
| `uvicorn[standard]` | ≥0.30 | ASGI 服务器 |
| `pydantic` | ≥2.0 | schema 校验（复用各业务模块的模型） |
| `python-multipart` | ≥0.0.9 | 表单支持 |
| `apscheduler` | ≥3.10 | 可选：APScheduler 内存任务调度（不复用 macOS launchd，仅供 API 触发的临时任务） |

**不引入**：SQLAlchemy（直接用业务模块的 SQLite 连接）、Celery（无分布式需求）、Redis（无并发）。

---

## 2. 数据模型

### 统一响应包装
```python
class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "ok"
    data: T | None = None

class ErrorResponse(BaseModel):
    code: int
    message: str
    detail: dict | None = None
```

### 任务状态（in-memory + SQLite 持久化）
```python
class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"

class Job(BaseModel):
    job_id: str
    type: Literal["refresh-data", "backtest", "analyze", "regenerate"]
    status: JobStatus
    progress: float  # 0-1
    started_at: datetime
    finished_at: datetime | None
    result: dict | None
    error: str | None
```

### 周期分析响应
```python
class PeriodReturn(BaseModel):
    period: Literal["daily","weekly","monthly","quarterly","yearly"]
    labels: list[str]   # ["2026-01","2026-02",...]
    returns: list[float]
    benchmark_returns: list[float]  # 沪深300

class NavCurve(BaseModel):
    dates: list[date]
    nav: list[float]
    drawdown: list[float]  # 负数
    benchmark_nav: list[float]
```

---

## 3. 接口契约（路由分组）

```python
# src/api/app.py
app = FastAPI(title="TrandeAgent API", version="1.0")

# 路由分组
app.include_router(funds.router,       prefix="/api/funds",       tags=["funds"])
app.include_router(strategies.router,  prefix="/api/strategies",  tags=["strategies"])
app.include_router(discover.router,    prefix="/api/discover",    tags=["discover"])
app.include_router(observation.router, prefix="/api/observation", tags=["observation"])
app.include_router(config.router,      prefix="/api/config",      tags=["config"])
app.include_router(jobs.router,        prefix="/api/jobs",        tags=["jobs"])
app.include_router(system.router,      prefix="/api/system",      tags=["system"])
```

### 关键端点实现策略

| 端点 | 实现 |
|---|---|
| `GET /api/funds/{code}` | 调 `IndicatorEngine.calc_all(code)` |
| `GET /api/funds/{code}/nav` | 调 `DataProvider.get_nav(code)`，按日期过滤 |
| `POST /api/funds/{code}/analyze` | 创建 Job → `BackgroundTasks.add_task(FundAnalyzer.analyze, code)` |
| `GET /api/strategies/{id}/timeseries` | 用 `pandas.resample` 计算多周期收益 |
| `PUT /api/config` | 调 `ConfigManager.save_with_commit` → 返回 ChangeImpact |

---

## 4. 依赖列表

- 上游：#1 data-provider, #4 indicators, #5 screener, #6 analyzer, #7 signal, #8 arena, #9 config
- 模块内：无（只做协议转换）
- 下游：#10 Mac 前端

---

## 5. 测试策略

| 层级 | 工具 | 覆盖点 |
|---|---|---|
| 单元 | pytest + httpx | 每个端点 happy path + 错误码 |
| 集成 | pytest + 真实业务模块 mock | 端到端 API 流程 |
| 异步任务 | pytest-asyncio | Job 创建/查询/完成 |
| OpenAPI | openapi-typescript（npm） | 生成的 TS 类型可编译 |
| 性能 | locust（可选） | 列表 API P95 ≤ 2s |

覆盖率 > 85%。

---

## 6. 关键决策（小 ADR）

### 为什么 FastAPI 而不是 Flask
- 原生 async + Pydantic + OpenAPI 三合一
- 类型即文档，前端自动生成 TS 类型

### 为什么任务用 BackgroundTasks 而不是 Celery
- 本地单进程，无分布式需求
- BackgroundTasks 零额外组件
- 任务状态用 SQLite 持久化（重启可查）

### 为什么净值 API 默认分页
- 5 年 × 8000 基金 = 海量数据
- 前端按需加载（图表只画当前选中基金）
- `?page=1&size=250` 默认 250 天/页

---

## 7. 目录结构

```
src/api/
├── __init__.py
├── app.py                  # FastAPI 应用 + 路由注册
├── deps.py                 # 依赖注入（DataProvider/IndicatorEngine 单例）
├── schema.py               # ApiResponse/ErrorResponse/Job/PeriodReturn
├── routers/
│   ├── funds.py
│   ├── strategies.py
│   ├── discover.py
│   ├── observation.py
│   ├── config.py
│   ├── jobs.py
│   └── system.py
├── services/               # 薄封装，调业务模块
│   ├── fund_service.py
│   ├── strategy_service.py
│   └── job_service.py
└── __main__.py             # python -m src.api → uvicorn 启动

tests/api/
├── conftest.py             # pytest fixtures
├── test_funds.py
├── test_strategies.py
└── test_jobs.py
```

---

## 变更记录

| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v0.1 | 2026-07-06 | plan 初稿 | 小瑶 |
