# Feature #7 — signal-engine 实施计划

> 含 5 要素

---

## 1. 技术选型

| 库 | 用途 |
|---|---|
| `pandas-ta` | 技术指标（MA/MACD/RSI/布林） |
| 复用 #4 | PE 分位、回撤等 |
| `pydantic` | 信号 schema |

---

## 2. 数据模型

```python
class SignalRule(BaseModel):
    name: str
    category: Literal["technical", "fundamental", "fund_specific"]
    indicator: str
    operator: str
    threshold: float
    weight: float = 1.0

class Signal(BaseModel):
    fund_code: str
    date: date
    level: Literal["加仓", "持有", "减仓", "止损"]
    reasons: list[str]  # 每条含【依据：指标=值】
    score: float        # 加权得分
```

---

## 3. 接口契约
```python
class SignalEngine(ABC):
    @abstractmethod
    def calc_signals(self, fund_codes: list[str], rules: list[SignalRule]) -> list[Signal]: ...
    @abstractmethod
    def detect_intraday_alert(self, fund_code: str, daily_return: float) -> bool: ...
```

---

## 4. 依赖
- 上游：#1, #4, #2
- 下游：#8

---

## 5. 测试策略
- 单元：每个信号规则独立测试
- 集成：观察池 10 只基金端到端
- 去噪：24h 内同档信号合并
- 性能：50 只 ≤ 10s

覆盖率 > 80%。

---

## 6. 关键决策
- 信号权重默认均分（用户可在 YAML 配置）
- 大跌阈值 -3% 全基金类型统一（用户可改）

---

## 7. 目录结构
```
src/signal/
├── __init__.py
├── engine.py
├── technical.py      # 技术面信号
├── fundamental.py    # 基本面信号
├── fund_specific.py  # 基金专属信号
├── synthesizer.py    # 综合合成
└── __main__.py
```

---

## 变更记录
| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v0.1 | 2026-07-06 | plan 初稿 | 小瑶 |
