# Feature #5 — fund-screener 实施计划

> 含 5 要素（精简版）

---

## 1. 技术选型
- `pydantic` 规则 schema
- `pyyaml` 规则加载
- `pandas` 筛选 + 打分
- 复用 #2 feishu-io 写 Base

## 2. 数据模型
```python
class Rule(BaseModel):
    name: str
    field: str
    op: Literal[">=", "<=", "between", "in", "percentile_top"]
    value: float | list | str

class ScreenerConfig(BaseModel):
    rules: list[Rule]
    weights: dict[str, float]
    top_n: int = 20
```

## 3. 接口契约
```python
class FundScreener(ABC):
    def screen(self, config: ScreenerConfig, all_indicators: pd.DataFrame) -> pd.DataFrame: ...
    def explain(self, fund_code: str, matched_rules: list) -> str: ...
```

## 4. 依赖
- 上游：#1, #4
- 下游：#7

## 5. 测试策略
- 单元：每条规则独立测试
- 集成：4433 法则端到端
- 性能：全市场 ≤ 30s

## 6. 关键决策
- 规则用 YAML 而非 DSL（用户可读）
- 综合得分 = 命中规则数 × 权重之和

## 7. 目录结构
```
src/screener/
├── __init__.py
├── engine.py
├── rules.py
├── scorer.py
└── __main__.py
```

---

## 变更记录
| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v0.1 | 2026-07-06 | plan 初稿 | 小瑶 |
