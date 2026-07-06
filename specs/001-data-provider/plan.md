# Feature #1 — data-provider 实施计划

> **Spec-Kit plan 产出** | Step 5.2 第③步
> 上游：[spec.md](./spec.md) · 下游：[tasks.md](./tasks.md)
> **本文档是技术选型唯一归宿**（spec.md 不写技术）。
> 必须含 5 项要素：技术选型 / 数据模型 / 接口契约 / 依赖列表 / 测试策略。

---

## 1. 技术选型

### 1.1 语言与运行时
- **Python 3.11+**（match 整个项目的语言选择，见 [adr.md ADR-001](../docs/adr.md)）
- 包管理：`uv`（比 pip/poetry 快 10×，零配置）

### 1.2 数据源库
| 库 | 版本 | 用途 | 理由 |
|---|---|---|---|
| `akshare` | ≥1.14 | 主数据源 | 字段全覆盖、零成本（见 research.md §1.5） |
| `pandas` | ≥2.2 | DataFrame | 业内标准 |
| `pyarrow` | ≥15 | Parquet IO | 列式存储，回测场景快 5× |
| `tenacity` | ≥8.0 | 重试 | 指数退避 |
| `loguru` | ≥0.7 | 日志 | 简单可靠 |
| `pydantic` | ≥2.0 | schema 校验 | 元数据模型 |

### 1.3 缓存格式（Clarify Q1 落锁）
| 数据类型 | 格式 | 文件组织 | 理由 |
|---|---|---|---|
| **日频净值** | Parquet | `data/cache/nav/{fund_code}.parquet` | 列式压缩，回测时批量读极快（VectorBT/Backtrader 都吃 Parquet） |
| **基金元数据** | SQLite | `data/cache/meta.db` 表 `fund_basic` | 关系查询灵活，更新单条快 |
| **季度持仓** | Parquet | `data/cache/holdings/{fund_code}.parquet` | 列式，按季度追加 |
| **经理信息** | SQLite | `data/cache/meta.db` 表 `fund_manager` | 关系结构（一人管多基金） |
| **新鲜度报告** | SQLite | `data/cache/meta.db` 表 `data_freshness` | 关系查询，统计方便 |

### 1.4 不引入的库（避免过度工程）
- ❌ Tushare（积分门槛高，本项目用量级用不到）
- ❌ Redis（无并发需求）
- ❌ Celery（单进程足够）
- ❌ DuckDB（用 SQLite 足够，引入新学习成本）

---

## 2. 数据模型

### 2.1 SQLite 表结构（`data/cache/meta.db`）

#### 表 `fund_basic`（基金基本信息）
```sql
CREATE TABLE fund_basic (
    fund_code        TEXT PRIMARY KEY,        -- 基金代码 '000001'
    fund_name        TEXT NOT NULL,            -- 基金简称 '华夏成长混合'
    fund_type        TEXT NOT NULL,            -- 类型 '混合型-偏股'
    fund_category    TEXT NOT NULL,            -- 大类: 'qdii'|'index'|'etf_link'|'active_stock'
    pinyin_abbr      TEXT,                     -- 拼音缩写
    manager_names    TEXT,                     -- 现任经理（逗号分隔）
    management_co    TEXT,                     -- 基金管理人
    custodian_co     TEXT,                     -- 托管人
    establish_date   DATE,                     -- 成立日
    latest_scale     REAL,                     -- 最新规模（亿元）
    management_fee   REAL,                     -- 管理费率
    custodian_fee    REAL,                     -- 托管费率
    history_months   INTEGER,                  -- 历史月数（Clarify Q2）
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_fund_basic_category ON fund_basic(fund_category);
```

#### 表 `fund_manager`（经理信息）
```sql
CREATE TABLE fund_manager (
    manager_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    manager_name     TEXT NOT NULL,
    fund_code        TEXT NOT NULL,
    start_date       DATE,                     -- 任期起始
    end_date         DATE,                     -- 任期结束（NULL=现任）
    tenure_years     REAL,                     -- 任期年数
    total_assets     REAL,                     -- 在管总规模（亿）
    FOREIGN KEY (fund_code) REFERENCES fund_basic(fund_code)
);
CREATE INDEX idx_fund_manager_code ON fund_manager(fund_code);
```

#### 表 `data_freshness`（新鲜度报告）
```sql
CREATE TABLE data_freshness (
    fund_code        TEXT NOT NULL,
    field_name       TEXT NOT NULL,            -- 'nav'|'manager'|'holdings'
    last_update      DATE,                     -- 最近成功更新日
    is_stale         BOOLEAN DEFAULT 0,        -- 是否过期（用缓存降级）
    source           TEXT,                     -- 'cache'|'fresh'|'failed'
    fail_reason      TEXT,                     -- 失败原因
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (fund_code, field_name)
);
```

### 2.2 Parquet 文件 schema

#### `nav/{fund_code}.parquet`（日频净值）
| 列 | 类型 | 说明 |
|---|---|---|
| trade_date | DATE | 交易日 |
| unit_nav | FLOAT | 单位净值 |
| accum_nav | FLOAT | 累计净值 |
| daily_return | FLOAT | 日涨跌幅（百分比） |
| is_adjusted | BOOL | 是否前复权（默认 True） |

- 按季度分区文件可选拟能优化（先单文件，性能不够再分）
- 排序键：`trade_date ASC`

#### `holdings/{fund_code}.parquet`（季度持仓）
| 列 | 类型 | 说明 |
|---|---|---|
| report_date | DATE | 季报日期 |
| stock_code | TEXT | 重仓股代码 |
| stock_name | TEXT | 重仓股名称 |
| holding_pct | FLOAT | 持仓比例 |
| industry | TEXT | 所属行业 |

---

## 3. 接口契约

### 3.1 `DataProvider` 抽象基类

```python
from abc import ABC, abstractmethod
from datetime import date
from typing import Literal
import pandas as pd

FundCategory = Literal["qdii", "index", "etf_link", "active_stock"]

class DataProvider(ABC):
    """数据访问层抽象。下游所有模块只依赖此接口。"""

    @abstractmethod
    def list_funds(self, categories: list[FundCategory] | None = None) -> pd.DataFrame:
        """列出基金基本信息。None=全部已支持的 4 类（不含债基/货基）。"""

    @abstractmethod
    def get_nav(self, fund_code: str, start: date, end: date) -> pd.DataFrame:
        """获取日频净值序列。命中缓存不发起网络请求。"""

    @abstractmethod
    def get_manager(self, fund_code: str) -> pd.DataFrame:
        """获取基金历任经理信息。"""

    @abstractmethod
    def get_holdings(self, fund_code: str, report_date: date | None = None) -> pd.DataFrame:
        """获取季度持仓。None=所有可得季报。"""

    @abstractmethod
    def refresh_incremental(self, fund_codes: list[str] | None = None) -> dict:
        """增量更新。None=全市场。返回新鲜度报告 dict。"""

    @abstractmethod
    def refresh_full_backfill(self, fund_codes: list[str], years: int = 5) -> dict:
        """首次全量回填（手动触发，异步后台跑）。"""

    @abstractmethod
    def get_freshness_report(self) -> pd.DataFrame:
        """查询新鲜度报告。"""
```

### 3.2 `AkShareProvider` 实现要点

- 构造函数接受 `cache_dir: Path = Path("data/cache")`
- 内部维护 `_rate_limiter`（默认 1 req/s）
- 内部维护 `_ua_rotator`（10 个 User-Agent 轮换）
- 所有上游调用走 `tenacity.retry`（3 次，指数退避 1-2-4s）
- 失败后降级到缓存，标记 `is_stale=True`

### 3.3 命令行入口（Clarify Q5 — plan 阶段确定）

```bash
# 增量更新（每日盘后由 launchd 调用）
python -m src.data refresh

# 首次全量回填（异步后台）
python -m src.data backfill --years 5

# 查看新鲜度
python -m src.data status

# 仅刷新某只基金
python -m src.data refresh --codes 000001,161725
```

### 3.4 异步后台执行（Clarify Q6 落锁）
- 首次启动检测到 `data/cache/` 为空 → 起一个 `threading.Thread` 后台跑 `refresh_full_backfill`
- 前台立即返回 5 只样例基金（华夏成长/招商白酒/易方达蓝筹/中欧时代先锋/富国天惠）30 天数据
- 后台任务进度写入 `data/cache/.backfill_progress.json`
- 完成后通过日志通知

---

## 4. 依赖列表

### 4.1 上游依赖（外部）
| 依赖 | 版本 | 说明 |
|---|---|---|
| AkShare | ≥1.14 | 公开开源，无需 token |
| Python | ≥3.11 | match-language |
| macOS | 13+ | 本地运行环境 |

### 4.2 模块内依赖
- 无（基础设施层）

### 4.3 下游依赖本 feature
| Feature | 用到的接口 |
|---|---|
| #4 indicators | `get_nav`, `get_holdings` |
| #5 fund-screener | `list_funds`, `get_manager` |
| #6 fund-analyzer | 全部接口 |
| #7 signal-engine | `get_nav` |
| #8 strategy-arena | `get_nav`（5 年历史） |

---

## 5. 测试策略

### 5.1 单元测试（pytest，覆盖率目标 > 80%）

| 测试类 | 覆盖点 |
|---|---|
| `TestRateLimiter` | 1 req/s 限速、并发 ≤1 |
| `TestUARotator` | 10 个 UA 轮换 |
| `TestRetryStrategy` | 3 次重试、指数退避、最终失败降级 |
| `TestAkShareProvider` | 各接口 happy path |
| `TestCache` | Parquet 写入/读取、SQLite CRUD、缓存命中 |
| `TestFreshnessReport` | 新鲜度报告字段完整性 |
| `TestCategoryFilter` | 4 类基金过滤（剔除债基/货基） |

### 5.2 集成测试（不打真实网络，用 fixture）

| 测试 | 说明 |
|---|---|
| `test_full_workflow_with_fixtures` | mock AkShare 返回，跑完"全量→增量→查询"全流程 |
| `test_failure_degradation` | mock 接口超时，验证降级到缓存 |
| `test_async_backfill` | mock 空缓存启动，验证后台异步 + 前台返回样例 |

### 5.3 烟雾测试（可选，手动）

`scripts/smoke_test_data.py`：真实拉取 10 只基金 30 天数据，跑通端到端。

### 5.4 性能基准（AC 验证）

```python
# tests/perf/test_perf.py
def test_first_full_backfill_under_3_hours():
    """AC-1: 首次全量 ≤ 3 小时"""

def test_incremental_under_20_minutes():
    """AC-2: 增量 ≤ 20 分钟"""
```

---

## 6. 关键技术决策（plan 内的小 ADR）

### 6.1 为什么用 Parquet 而不是单一 SQLite？
- 净值数据是典型时序，按代码分文件后，回测 50-200 策略 × 8000 基金时，Parquet 列式读比 SQLite 行式快 5-10×
- SQLite 用于元数据（关系结构），不用来存时序

### 6.2 为什么用 threading 而不是 asyncio？
- AkShare 是同步库，asyncio 反而需要 `run_in_executor` 包一层，收益低
- 单个后台线程跑全量回填足够

### 6.3 为什么 UA 轮换？
- 东方财富对相同 UA + 高频访问会临时封 IP（30 分钟）
- 10 个真实浏览器 UA 轮换可显著降低封禁率（research.md §1.2）

### 6.4 为什么不引入 Tushare 作为降级？
- 调研结论（research.md §1.5）：本项目用量级不会触发 AkShare 限流到失效
- 架构上保留 `DataProvider` 接口，未来需要时可平滑插入 `TushareProvider`

---

## 7. 风险与缓解

| 风险 | 缓解 |
|---|---|
| AkShare 接口 break（上游改版） | 单元测试覆盖关键接口；mock fixture 隔离；多接口降级（如净值挂了用 ETF 接口） |
| Parquet 写入并发冲突 | 单写入线程，读多写少 |
| 后台回填失败无感知 | 进度文件 + 日志 + 启动时检测异常中断 |
| 缓存膨胀（5 年 × 8000 基金 ≈ 2GB） | 按代码分文件，可单独删除；定期归档冷数据 |

---

## 8. 目录结构（最终）

```
src/data/
├── __init__.py
├── provider.py              # DataProvider 抽象
├── akshare_provider.py      # AkShareProvider 实现
├── cache.py                 # Parquet + SQLite 缓存
├── freshness.py             # 新鲜度报告
├── rate_limit.py            # 限流 + UA 轮换
└── __main__.py              # CLI 入口（refresh/backfill/status）

data/cache/                  # 运行时产物（gitignore）
├── nav/
│   ├── 000001.parquet
│   └── ...
├── holdings/
├── meta.db
└── .backfill_progress.json

tests/data/
├── test_provider.py
├── test_cache.py
├── test_rate_limit.py
├── test_freshness.py
├── conftest.py              # mock fixtures
└── fixtures/
    └── akshare_mock.json    # mock 上游响应
```

---

## 变更记录

| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v0.1 | 2026-07-06 | plan 初稿，含 5 要素 | 小瑶 |
