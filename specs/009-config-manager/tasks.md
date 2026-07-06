# Feature #9 — config-manager 任务清单

> 任务总数：**12 条**

| # | 任务 | 依赖 | 难度 |
|---|---|---|---|
| T01 | AppConfig Pydantic schema（聚合 #5/#7/#8） | - | 中等 |
| T02 | ConfigManager 抽象接口 | T01 | 容易 |
| T03 | 实现 loader（YAML + 环境变量替换） | T01 | 容易 |
| T04 | 实现 validate（错误 + 行号） | T01 | 中等 |
| T05 | 实现 impact（screener 影响） | T01,#5 | 中等 |
| T06 | 实现 impact（signal 影响） | T01,#7 | 中等 |
| T07 | 实现 impact（arena 影响提示重跑） | T01 | 容易 |
| T08 | 实现 version（git commit / log / rollback） | T02 | 中等 |
| T09 | 实现 save_with_commit | T04,T08 | 中等 |
| T10 | CLI 入口（validate/impact/log/rollback） | T09 | 容易 |
| T11 | 生成 example 配置 | T01 | 容易 |
| T12 | 单元 + 集成测试 | T05-T10 | 中等 |

## 执行顺序
```
T01 → T02 → T03,T04
              ↓
        T05,T06,T07 并行
              ↓
        T08 → T09 → T10 → T11
                          ↓
                        T12
```

## 变更记录
| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v0.1 | 2026-07-06 | tasks 初稿 | 小瑶 |
