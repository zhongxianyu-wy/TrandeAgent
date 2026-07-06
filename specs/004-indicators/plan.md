# Feature #4 — indicators 实施计划

> 含 5 要素

---

## 1. 技术选型

| 库 | 版本 | 用途 |
|---|---|---|
| `empyrical` | ≥0.5.5 | 风险指标（夏普/回撤/α/β） |
| `quantstats` | ≥0.0.62 | 报告 + 交叉验证 |
| `pandas-ta` | ≥0.3.14b | 技术指标（MA/MACD/RSI） |
| `numba` | ≥0.59 | 性能加速（批量计算） |
| `concurrent.futures` | 内置 | 并行批量 |

---

## 2. 数据模型

### 指标缓存 SQLite 表（`data/cache/meta.db`）
```sql
CREATE TABLE indicator_cache (
    fund_code TEXT, as_of_date DATE, layer TEXT,
    indicators JSON,
    PRIMARY KEY (fund_code, as_of_date, layer)
);
```

### Pydantic 模型
```python
class L1Basic(BaseModel):
    scale: float; establish_years: float
    manager_tenure_years: float
    institution_holding_pct: float
    management_fee: float; custodian_fee: float

class L2Performance(BaseModel):
    return_1y: float; return_3y: float; return_5y: float
    rank_1y_percentile: float
    max_drawdown: float; sharpe: float
    volatility: float; alpha: float; beta: float

class L3Style(BaseModel):
    style_box: str
    industry_concentration_top3: float
    holding_turnover: float
    style_drift_score: float

class L4Cashflow(BaseModel):
    share_change_yoy: float
    institution_holding_change: float
    dividend_count_5y: int

class FundIndicators(BaseModel):
    fund_code: str; as_of_date: date
    L1_basic: L1Basic
    L2_performance: L2Performance
    L3_style: L3Style
    L4_cashflow: L4Cashflow
    rating: int  # 1-5
```

---

## 3. 接口契约

```python
class IndicatorEngine(ABC):
    @abstractmethod
    def calc_all(self, fund_code: str, end: date, years: int = 5) -> FundIndicators: ...
    @abstractmethod
    def calc_batch(self, fund_codes: list[str], end: date) -> pd.DataFrame: ...
    @abstractmethod
    def get_rating(self, indicators: FundIndicators) -> int: ...
```

---

## 4. 依赖
- 上游：#1 data-provider（DataProvider 接口）
- 下游：#5/#6/#7/#8

---

## 5. 测试策略
- 单元：每层指标独立测试（与 empyrical/quantstats 对比）
- 集成：calc_batch 100 只基金
- 缓存：同日重复走缓存
- 性能：AC-2 30s 上限

覆盖率 > 80%。

---

## 6. 关键决策
- L1-L4 解耦，每层独立测试
- 评级用规则加权（参考晨星，简化为 5 个维度）
- 缓存粒度：按 (fund_code, as_of_date, layer)

---

## 7. 目录结构
```
src/indicators/
├── __init__.py
├── engine.py              # IndicatorEngine 抽象
├── L1_basic.py
├── L2_performance.py
├── L3_style.py
├── L4_cashflow.py
├── rating.py
└── cache.py
```

---

## 变更记录
| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v0.1 | 2026-07-06 | plan 初稿 | 小瑶 |
