# Feature #11 — api-backend 任务清单

> 任务总数：**15 条**

| # | 任务 | 依赖 | 难度 |
|---|---|---|---|
| T01 | FastAPI 应用骨架 + 路由注册 + CORS | - | 容易 |
| T02 | Pydantic schema（ApiResponse/Job/PeriodReturn/NavCurve） | - | 容易 |
| T03 | 依赖注入（DataProvider/IndicatorEngine 等单例） | T01 | 中等 |
| T04 | 实现 funds 路由（5 个端点） | T03 | 中等 |
| T05 | 实现 strategies 路由（7 个端点） | T03 | 中等 |
| T06 | 实现 discover 路由 | T03 | 容易 |
| T07 | 实现 observation 路由（含同步飞书 Base） | T03 | 中等 |
| T08 | 实现 config 路由（含影响范围检测） | T03,#9 | 中等 |
| T09 | 实现 jobs 路由（BackgroundTasks + SQLite 状态） | T02 | 困难 |
| T10 | 实现 system 路由（status/health） | T03 | 容易 |
| T11 | 实现周期分析数据计算（pandas.resample） | T02 | 中等 |
| T12 | 统一错误处理 + ValidationError → 422 | T01 | 中等 |
| T13 | OpenAPI 类型生成脚本（openapi-typescript） | T01 | 容易 |
| T14 | 单元 + 集成测试（覆盖率 > 85%） | T04-T10 | 中等 |
| T15 | 性能基准（P95 ≤ 500ms） | T14 | 中等 |

## 执行顺序

```
T01,T02 并行
  ↓
T03 → T04,T05,T06,T07,T08,T10 并行
              ↓
            T09（异步任务核心）
              ↓
            T11,T12 → T13
                      ↓
                    T14 → T15
```

## 变更记录

| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v0.1 | 2026-07-06 | tasks 初稿 | 小瑶 |
