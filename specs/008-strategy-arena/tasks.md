# Feature #8 — strategy-arena 任务清单

> 任务总数：**18 条**（核心创新模块，最复杂）

| # | 任务 | 依赖 | 难度 |
|---|---|---|---|
| T01 | Strategy/BacktestResult/ForwardResult/ArenaRanking Pydantic 模型 | - | 容易 |
| T02 | 设计 strategy_prototypes.yaml（15 原型） | - | 中等 |
| T03 | 设计 mind_models.yaml（8 大师原文要点） | - | 中等 |
| T04 | 设计差异维度矩阵 YAML | - | 中等 |
| T05 | StrategyGenerator 抽象接口 | T01 | 容易 |
| T06 | 实现 LLM 策略生成器（差异维度约束） | T02,T03,T04,T05,#6 | 困难 |
| T07 | 实现去重（cosine 距离 < 0.1） | T06 | 中等 |
| T08 | 实现 15 个原型 Python 类 | T02 | 困难 |
| T09 | BacktestRunner 抽象接口 | T01 | 容易 |
| T10 | 实现 VectorBTRunner（参数扫描） | T08,T09 | 困难 |
| T11 | 实现 BacktraderRunner（精细回测） | T08,T09 | 困难 |
| T12 | 实现 Top-20 精细回测触发逻辑 | T10,T11 | 中等 |
| T13 | 实现 ForwardSimulator（每日更新） | T01 | 中等 |
| T14 | 实现 30 天 qualified 判定 | T13 | 容易 |
| T15 | 实现双轨交叉验证（差异 > 20% 标记） | T10,T13 | 中等 |
| T16 | 实现 ArenaRanker（8 领域 Top-5） | T01 | 中等 |
| T17 | 集成 #2 写飞书 Base + 策略采用入口 | T16 | 中等 |
| T18 | 单元 + 集成 + 性能 + 防幻觉测试 | T06-T16 | 困难 |

## 执行顺序
```
T01,T02,T03,T04 并行起步
       ↓
T05,T08,T09 三线
       ↓
T06 → T07         T10,T11 → T12
                          ↓
              T13 → T14 → T15
                          ↓
                       T16 → T17
                          ↓
                        T18
```

关键路径：T02 → T08 → T10 → T12 → T15 → T16 → T17 → T18

## 变更记录
| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v0.1 | 2026-07-06 | tasks 初稿 | 小瑶 |
