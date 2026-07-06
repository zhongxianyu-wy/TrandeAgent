# Feature #1 — data-provider 任务清单

> **Spec-Kit tasks 产出** | Step 5.2 第④步
> 上游：[spec.md](./spec.md) · [plan.md](./plan.md)
> 任务总数：**15 条**（符合 12-18 区间，粒度适中）
> 每条任务含：验收标准 + 依赖 + 预估难度（容易/中等/困难）

---

## 任务总览

| # | 任务 | 依赖 | 难度 |
|---|---|---|---|
| T01 | 项目脚手架与依赖初始化 | - | 容易 |
| T02 | 配置加载与日志 | T01 | 容易 |
| T03 | 实现 RateLimiter + UARotator | T01 | 中等 |
| T04 | 实现 RetryStrategy | T01 | 中等 |
| T05 | 定义 DataProvider 抽象接口 | T01 | 容易 |
| T06 | 实现 SQLite 缓存层 | T02 | 中等 |
| T07 | 实现 Parquet 缓存层 | T02 | 中等 |
| T08 | 实现 FreshnessReport | T06 | 容易 |
| T09 | 实现 AkShareProvider 核心（list/manager） | T05,T06,T07,T08,T03,T04 | 中等 |
| T10 | 实现 AkShareProvider 时序接口（nav/holdings） | T09 | 中等 |
| T11 | 实现 category 4 类过滤 | T09 | 容易 |
| T12 | 实现 CLI 入口（refresh/backfill/status） | T09,T10 | 中等 |
| T13 | 异步后台首次回填 | T12 | 困难 |
| T14 | 单元测试 + fixture（覆盖率 > 80%） | T09,T10,T11 | 中等 |
| T15 | 集成测试 + 性能基准（AC-1 ~ AC-5） | T13,T14 | 中等 |

---

## 详细任务

### T01：项目脚手架与依赖初始化
**做什么：** 用 `uv init` 初始化 Python 项目，添加 plan §1.2 全部依赖
**AC：**
- `pyproject.toml` 含 akshare/pandas/pyarrow/tenacity/loguru/pydantic
- `python -c "import akshare"` 成功
- 目录结构对齐 plan §8
**依赖：** 无
**难度：** 容易

---

### T02：配置加载与日志
**做什么：**
- 用 Pydantic 定义 `DataConfig`（cache_dir、rate_limit、retry 次数、UA 池）
- 从 `config/data.yaml` 加载
- loguru 配置：本地文件轮转 + 控制台输出
**AC：**
- `from src.data import DataConfig` 可用
- 日志输出到 `logs/data-{date}.log`
**依赖：** T01
**难度：** 容易

---

### T03：实现 RateLimiter + UARotator
**做什么：**
- `RateLimiter`: 1 req/s 限速，线程安全（用 `threading.Lock`）
- `UARotator`: 10 个真实浏览器 UA 循环
- 组合装饰器 `@rate_limited`
**AC：**
- 单测：1 秒内连续调用 ≤ 1 次成功
- 单测：UA 每次不同
**依赖：** T01
**难度：** 中等

---

### T04：实现 RetryStrategy
**做什么：**
- 用 `tenacity` 实现 3 次重试 + 指数退避（1-2-4s）
- 失败后抛 `UpstreamUnavailable` 异常
**AC：**
- 单测：mock 接口失败，重试 3 次
- 单测：3 次都失败抛 `UpstreamUnavailable`
**依赖：** T01
**难度：** 中等

---

### T05：定义 DataProvider 抽象接口
**做什么：** 按 plan §3.1 定义 ABC，含 7 个抽象方法
**AC：**
- `from src.data.provider import DataProvider` 可用
- 子类未实现抽象方法会抛 TypeError
**依赖：** T01
**难度：** 容易

---

### T06：实现 SQLite 缓存层
**做什么：**
- 建 `meta.db`（fund_basic / fund_manager / data_freshness 三表）
- CRUD 方法：`upsert_fund_basic`, `get_fund_basic`, `upsert_manager`, `get_manager`
- WAL 模式（读写并发）
**AC：**
- 单测：CRUD happy path
- 单测：重复 upsert 不报错
**依赖：** T02
**难度：** 中等

---

### T07：实现 Parquet 缓存层
**做什么：**
- `write_nav(fund_code, df)`：追加写，按 trade_date 去重
- `read_nav(fund_code, start, end)`：日期过滤读取
- holdings 同理
**AC：**
- 单测：写入后读取数据一致
- 单测：重复写入相同日期去重
- 单测：日期范围过滤正确
**依赖：** T02
**难度：** 中等

---

### T08：实现 FreshnessReport
**做什么：**
- 每次拉取后写入 `data_freshness` 表
- `get_freshness_report()` 返回 DataFrame
- 字段：fund_code, field_name, last_update, is_stale, source, fail_reason
**AC：**
- 单测：fresh/cache/failed 三种 source 都能写入
- 单测：查询能按 is_stale 过滤
**依赖：** T06
**难度：** 容易

---

### T09：实现 AkShareProvider 核心（list_funds / get_manager）
**做什么：**
- `list_funds(categories)`: 调 `ak.fund_name_em()` + 类型映射
- `get_manager(fund_code)`: 调 `ak.fund_manager_em()`
- 写入 SQLite 缓存 + 更新鲜度
**AC：**
- 集成测试（mock akshare）：返回 5 只基金样例
- 单测：4 类过滤正确（剔除债基/货基）
**依赖：** T05, T06, T07, T08, T03, T04
**难度：** 中等

---

### T10：实现 AkShareProvider 时序接口（get_nav / get_holdings）
**做什么：**
- `get_nav(fund_code, start, end)`: 调 `ak.fund_open_fund_info_em()`
- `get_holdings(fund_code, report_date)`: 调 `ak.fund_portfolio_hold_em()`
- 缓存命中优先；缓存缺失走 `rate_limited + retried` 上游调用
**AC：**
- 集成测试（mock）：返回 30 天净值
- 单测：缓存命中不发请求
- 单测：缓存缺失走上游并写入缓存
**依赖：** T09
**难度：** 中等

---

### T11：实现 category 4 类过滤
**做什么：**
- AkShare 返回的"混合型-偏股"等字符串映射到 `fund_category`（active_stock/index/etf_link/qdii）
- 显式剔除：债基/货基/FOF/REITs
**AC：**
- 单测：4 类样本全部正确分类
- 单测：债基/货基被剔除
**依赖：** T09
**难度：** 容易

---

### T12：实现 CLI 入口（refresh / backfill / status）
**做什么：**
- `python -m src.data refresh [--codes]`：增量更新
- `python -m src.data backfill --years 5`：全量回填
- `python -m src.data status`：打印新鲜度统计
**AC：**
- 手测：`python -m src.data refresh --codes 000001` 成功
- 手测：`python -m src.data status` 输出统计表
**依赖：** T09, T10
**难度：** 中等

---

### T13：异步后台首次回填
**做什么：**
- 检测 `data/cache/nav/` 为空 → 起 `threading.Thread` 后台跑 `refresh_full_backfill`
- 前台立即返回 5 只样例基金 30 天数据（mock fixture）
- 进度文件 `data/cache/.backfill_progress.json`（fund_count、progress_pct）
- 异常中断时下次启动检测并续跑
**AC：**
- 集成测试：mock 空缓存启动，验证前台立即返回 + 后台异步跑完
- 集成测试：模拟中断（kill 线程），重启后从进度文件续跑
**依赖：** T12
**难度：** 困难

---

### T14：单元测试 + fixture
**做什么：**
- `tests/data/conftest.py`：mock akshare 返回（用 fixture json）
- 覆盖 T03-T11 所有模块
- 目标覆盖率 > 80%（`pytest --cov=src/data`）
**AC：**
- `pytest tests/data/` 全绿
- 覆盖率报告 > 80%
**依赖：** T09, T10, T11
**难度：** 中等

---

### T15：集成测试 + 性能基准（AC-1 ~ AC-5）
**做什么：**
- AC-1：mock 全量回填（10 只基金 5 年），耗时统计
- AC-2：mock 增量，验证缓存命中 > 95%
- AC-3：mock 上游挂掉，验证降级
- AC-4：4 类过滤
- AC-5：同日重复运行幂等
**AC：**
- 5 个 AC 全部通过
- 真实烟雾测试（可选）：`scripts/smoke_test_data.py` 真实拉 10 只基金
**依赖：** T13, T14
**难度：** 中等

---

## 执行顺序

按依赖图：
```
T01 → T02 → T03,T04,T05,T06,T07,T08
                  ↓
                T09 → T10 → T11 → T12 → T13
                  ↓
                T14 → T15
```

**关键路径：** T01 → T02 → T06 → T09 → T10 → T12 → T13 → T15
**可并行：** T03/T04/T05 三个独立模块可并行做

---

## 变更记录

| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v0.1 | 2026-07-06 | tasks 初稿，15 条任务 | 小瑶 |
