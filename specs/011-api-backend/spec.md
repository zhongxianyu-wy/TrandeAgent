# Feature #11 — api-backend（FastAPI 本地后端 API）

> **Spec-Kit specify 产出** | v0.3 新增
> 来源：[PRD §6 F11](../docs/prd.md) · [context.md US-7~10](../docs/context.md)

---

## 1. Feature 简介

提供一个 FastAPI 本地后端，作为前端（Next.js）与业务模块（src.data/src.indicators/src.screener/src.analyzer/src.signal/src.arena）之间的统一查询与操作入口。**核心原则：API 层不重复实现业务逻辑，只做协议转换 + Pydantic schema 校验**。

---

## 2. 用户故事

- **作为前端**（Next.js），我需要一个标准 REST API，返回 JSON，不必直接读 SQLite/Parquet
- **作为前端**，我希望 API 有 OpenAPI 文档（/docs），能自动生成 TypeScript 类型
- **作为用户**，我希望前端操作（加观察池/采用策略/触发分析）通过 API 即时生效

---

## 3. 输入 / 输出

### 输入
- HTTP 请求（来自前端 localhost:3000）
- 业务模块调用（import 方式）

### 输出
- JSON 响应（Pydantic 校验过）
- OpenAPI 文档（/docs, /openapi.json）
- 错误响应（统一 schema：code/message/detail）

---

## 4. 功能需求（FR）

### FR-1：基金相关 API
- `GET /api/funds` 基金列表（支持 ?category=&domain=&search=&page=&size=）
- `GET /api/funds/{code}` 单基金详情（含 L1-L4 指标，来自 #4）
- `GET /api/funds/{code}/nav?start=&end=` 净值序列（用于前端画图）
- `GET /api/funds/{code}/report` 单基金 LLM 报告（来自 #6 缓存）
- `POST /api/funds/{code}/analyze` 触发 AI 重新分析（异步任务，返回 job_id）
- `GET /api/funds/{code}/holdings` 持仓明细
- `GET /api/funds/{code}/cashflow` 现金流（份额变动/机构持有）

### FR-2：策略竞技场 API
- `GET /api/strategies?domain=&sort=&page=` 策略列表（按领域分组+排名）
- `GET /api/strategies/{id}` 策略详情（含来源/参数/回测结果）
- `GET /api/strategies/{id}/timeseries?period=` 周期分析数据（多周期收益柱状图数据）
- `GET /api/strategies/{id}/nav?start=&end=&benchmark=` 净值曲线+回撤+基准对比
- `GET /api/strategies/{id}/cashflow` 现金流时序
- `POST /api/strategies/{id}/adopt` 采用策略 → 写入观察池
- `POST /api/strategies/{id}/disable` 停用策略
- `POST /api/strategies/regenerate` 重新生成策略（异步）

### FR-3：发现与推荐 API
- `GET /api/discover?domain=&window=today|week|month` 8 领域 × Top-5 推荐
- `GET /api/discover/reasons/{code}` 推荐理由详情

### FR-4：观察池 API
- `GET /api/observation` 观察池列表
- `POST /api/observation/{code}` 加入观察池（同时写本地 + 飞书 Base）
- `DELETE /api/observation/{code}` 移出观察池
- `GET /api/observation/{code}/signals` 该基金历史信号

### FR-5：配置管理 API（对应 #9）
- `GET /api/config` 当前配置
- `PUT /api/config` 更新配置（含影响范围检测，返回 ChangeImpact）
- `GET /api/config/history` 配置版本历史
- `POST /api/config/rollback/{commit}` 回滚

### FR-6：任务管理 API（手动触发）
- `POST /api/jobs/refresh-data` 触发数据刷新（来自 #1）
- `POST /api/jobs/backtest` 触发回测（来自 #8）
- `POST /api/jobs/analyze` 触发批量分析（来自 #6）
- `GET /api/jobs/{job_id}` 任务状态查询（status/progress/result）
- 任务用 BackgroundTasks 或 简单的 in-memory job 表

### FR-7：系统 API
- `GET /api/system/status` 系统状态（数据新鲜度/上次运行/活跃任务）
- `GET /api/system/health` 健康检查

### FR-8：CORS 与错误处理
- CORS 允许 `http://localhost:3000`
- 统一错误响应 `{code, message, detail}`
- Pydantic ValidationError → 422 + 详细字段错误

---

## 5. 非功能需求（NFR）

| 维度 | 要求 |
|---|---|
| 性能 | 查询 API P95 ≤ 500ms；列表 API ≤ 2s |
| 异步 | 长任务（分析/回测）走 BackgroundTasks，返回 job_id |
| 类型安全 | 所有响应 Pydantic 校验；OpenAPI 自动生成 |
| 文档 | `/docs` 可交互；`/openapi.json` 可被 openapi-typescript 消费 |
| CORS | 允许 localhost:3000 |
| 错误一致 | 统一错误 schema |

---

## 6. 验收标准（AC）

### AC-1：基金查询
**Given** 基金代码 000001
**When** `GET /api/funds/000001`
**Then**
1. 返回 L1-L4 全部指标
2. 响应时间 ≤ 500ms
3. Pydantic 校验通过

### AC-2：策略周期分析
**Given** 策略 ID
**When** `GET /api/strategies/{id}/timeseries?period=monthly`
**Then**
1. 返回月度收益序列
2. 含基准对比数据
3. ≤ 2s

### AC-3：触发分析（异步）
**Given** 基金代码
**When** `POST /api/funds/{code}/analyze`
**Then**
1. 立即返回 `{job_id}`
2. 后台跑 LLM 分析
3. `GET /api/jobs/{job_id}` 查询进度
4. 完成后 `GET /api/funds/{code}/report` 拿新报告

### AC-4：OpenAPI 类型生成
**Given** 后端启动
**When** `openapi-typescript http://localhost:8000/openapi.json -o frontend/types/api.ts`
**Then**
1. 生成 TypeScript 类型文件
2. 前端可直接 import 使用

### AC-5：CORS
**Given** 前端 localhost:3000
**When** fetch API
**Then** 无 CORS 错误

### AC-6：配置更新影响范围
**Given** 新配置
**When** `PUT /api/config`
**Then**
1. 返回 ChangeImpact（影响 N 只基金）
2. 自动 git commit

---

## 7. 显式不做

- ❌ 不做认证（本地单用户，无 login）
- ❌ 不做 GraphQL（REST 足够）
- ❌ 不做 WebSocket（MVP 用轮询查任务状态）
- ❌ 不重复实现业务逻辑（只调业务模块）

---

## 8. 依赖

- 前置：所有业务模块 #1-#9
- 下游：#10 Mac 前端

---

## 9. 开放问题

1. 任务状态用 in-memory 还是 SQLite 持久化（重启后可查）？
2. 净值数据量大（5 年 × 8000 基金），API 是否分页或按需加载？

---

## 变更记录

| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v0.1 | 2026-07-06 | specify 初稿 | 小瑶 |
