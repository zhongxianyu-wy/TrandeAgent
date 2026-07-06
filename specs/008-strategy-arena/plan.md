# Feature #8 — strategy-arena 实施计划

> 含 5 要素（核心创新模块，详细展开）

---

## 1. 技术选型

| 库 | 版本 | 用途 |
|---|---|---|
| `vectorbt` | ≥0.26 | 参数扫描（向量化极速） |
| `backtrader` | ≥1.9.78 | 精细回测（含手续费滑点） |
| `openai` SDK | ≥1.0 | 调 DeepSeek 生成策略 |
| `pydantic` | ≥2.0 | 策略 schema |
| `scikit-learn` | ≥1.4 | 参数空间去重（cosine 距离） |

复用 #6 fund-analyzer 的 LLMClient（强约束 prompt + 后校验）。

---

## 2. 数据模型

### `config/strategy_prototypes.yaml`（15 个原型）
```yaml
- id: proto_4433
  name: "4433法则"
  source: "邱显比教授"
  core_logic: "近1/2/3/5年排名前1/4 + 近3/6月排名前1/3"
  params_template:
    lookback_years: [1,2,3,5]
    percentile: 0.25
  domain: [价值, 成长, 红利, 指数增强]

- id: proto_dual_momentum
  name: "双动量"
  source: "Gary Antonacci《Dual Momentum Investing》"
  core_logic: "绝对动量+相对动量每月调仓"
  params_template:
    lookback_months: 12
  domain: [趋势, 全球配置]

# ... 共 15 个
```

### `config/mind_models.yaml`（8 位大师）
```yaml
- id: mind_buffett
  name: "巴菲特"
  works: ["伯克希尔股东信1958-2025", "《巴菲特致股东信》坎宁安编"]
  principles:
    - "市场先生（波动不是风险是机会）"
    - "安全边际（40美分买1美元）"
    - "护城河（品牌/规模/网络效应/转换成本）"
    - "能力圈（5分钟说不清就跳过）"
    - "逆向操作（贪婪恐惧反向）"
  strategy_mapping: "持仓集中Top-10>60% + ROE>15% + 消费金融龙头"
  domain: [价值]
  # ... 共 8 位
```

### 策略对象
```python
class Strategy(BaseModel):
    strategy_id: str              # "strat_001"
    prototype_id: str             # "proto_4433"
    mind_model_id: str | None     # "mind_buffett"
    domain: Literal[价值,成长,红利,趋势,逆向,全球配置,指数增强,低波]
    params: dict                  # 参数组合
    source_explanation: str       # 可追溯说明
    created_at: datetime

class BacktestResult(BaseModel):
    strategy_id: str
    annual_return: float
    sharpe: float
    max_drawdown: float
    win_rate: float
    calmar: float
    backtest_years: int

class ForwardResult(BaseModel):
    strategy_id: str
    forward_days: int
    forward_return: float
    daily_returns: list[float]
    is_qualified: bool  # >= 30 天

class ArenaRanking(BaseModel):
    strategy_id: str
    domain: str
    composite_score: float  # 收益×0.5 + 夏普×0.3 + 回撤倒数×0.2
    rank_in_domain: int
```

---

## 3. 接口契约

```python
class StrategyGenerator(ABC):
    @abstractmethod
    def generate(self, count: int, prototypes: list, mind_models: list, dim_matrix: dict) -> list[Strategy]: ...
    @abstractmethod
    def deduplicate(self, strategies: list[Strategy], threshold: float = 0.1) -> list[Strategy]: ...

class BacktestRunner(ABC):
    @abstractmethod
    def run_fast_scan(self, strategies: list[Strategy], years: int) -> list[BacktestResult]: ...
    @abstractmethod
    def run_precise(self, strategies: list[Strategy], years: int) -> list[BacktestResult]: ...

class ForwardSimulator(ABC):
    @abstractmethod
    def update_daily(self, date: date) -> None: ...
    @abstractmethod
    def is_qualified(self, strategy_id: str) -> bool: ...

class ArenaRanker(ABC):
    @abstractmethod
    def rank_by_domain(self, results: list) -> list[ArenaRanking]: ...
```

---

## 4. 依赖列表
- 上游：#1 data-provider, #4 indicators, #7 signal-engine, #2 feishu-io
- 模块内：复用 #6 LLMClient
- 下游：无

---

## 5. 测试策略

| 层级 | 覆盖点 |
|---|---|
| 单元：StrategyGenerator | 生成数量正确、参数在原型空间内、LLM 无发明 |
| 单元：去重 | cosine 距离 < 0.1 的策略被剔除 |
| 单元：VectorBT 回测 | 与 Backtrader 单策略对比误差 < 1% |
| 单元：ForwardSimulator | 满 30 天才 qualified |
| 单元：ArenaRanker | 8 领域各 Top-5 |
| 集成：端到端 | 100 策略全流程 ≤ 15 分钟 |
| 防幻觉 | 大师心智模型引用校验 |

覆盖率 > 80%（核心在生成器与回测引擎）。

---

## 6. 关键决策（小 ADR）

### 为什么 VectorBT + Backtrader 双引擎
- VectorBT 向量化：50-200 策略参数扫描秒级完成
- Backtrader 事件驱动：Top-20 精细回测含手续费/滑点
- 二者结果交叉验证（差异 < 5% 才可信）

### 为什么差异维度矩阵 5 维
- 投资域（8）× 择时逻辑（4）× 调仓频率（4）× 风控阈值（4）× 持仓集中度（4）= 2048
- 50-200 是 2048 的代表性子集，覆盖主要差异

### 为什么纸上模拟满 30 天才进 Top-5
- 防止回测过拟合（R8 风险）
- 30 个交易日 ≈ 1.5 月，足以过滤"幸运一周"

### 为什么大师心智模型仅取原文
- LLM 二次发挥会扭曲（R10 风险）
- 仅取公开著作原话作 ground truth

---

## 7. 目录结构
```
src/arena/
├── __init__.py
├── generator.py            # StrategyGenerator
├── deduplicator.py
├── backtest/
│   ├── runner.py           # BacktestRunner 抽象
│   ├── vectorbt_runner.py  # 快速扫描
│   └── backtrader_runner.py # 精细回测
├── forward.py              # ForwardSimulator
├── ranker.py               # ArenaRanker
├── strategies/             # 15 个原型实现
│   ├── base.py
│   ├── proto_4433.py
│   ├── proto_dual_momentum.py
│   └── ...
├── mind_models/            # 8 位大师数据加载
│   └── loader.py
└── __main__.py

config/
├── strategy_prototypes.yaml  # 15 原型
├── mind_models.yaml          # 8 大师
└── arena.yaml                # 竞技场配置

data/arena/                   # 运行时产物
├── strategies.parquet        # 策略清单
├── backtest_results.parquet
├── forward_results.parquet
└── rankings.parquet
```

---

## 变更记录
| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v0.1 | 2026-07-06 | plan 初稿 | 小瑶 |
