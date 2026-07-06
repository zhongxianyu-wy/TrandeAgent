# Feature #3 — scheduler 任务清单

> 任务总数：**12 条**

| # | 任务 | 依赖 | 难度 |
|---|---|---|---|
| T01 | Scheduler 抽象接口定义 | - | 容易 |
| T02 | 实现 holiday.py（chinese_calendar 封装） | T01 | 容易 |
| T03 | 实现 state.py（last_run + run_history） | T01 | 容易 |
| T04 | 实现 detect_missed_runs | T02,T03 | 中等 |
| T05 | 实现 backfill（含 5 天上限） | T04 | 中等 |
| T06 | 实现 record_run | T03 | 容易 |
| T07 | 设计 launchd plist 模板 | - | 中等 |
| T08 | 实现 LaunchdScheduler.install/uninstall | T07 | 中等 |
| T09 | 实现 LaunchdScheduler.is_installed | T08 | 容易 |
| T10 | 实现 CLI（install/uninstall/status/run --force） | T08,T09 | 中等 |
| T11 | scripts/install_launchd.sh 一键脚本 | T08 | 容易 |
| T12 | 单元 + 集成测试（覆盖率 > 85%） | T02-T10 | 中等 |

## 执行顺序
```
T01 → T02,T03 → T04 → T05,T06
T07 → T08 → T09 → T10
T11 独立
T12 收尾
```

## 变更记录
| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v0.1 | 2026-07-06 | tasks 初稿 | 小瑶 |
