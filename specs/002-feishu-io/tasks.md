# Feature #2 — feishu-io 任务清单

> 任务总数：**13 条**

---

## 任务总览

| # | 任务 | 依赖 | 难度 |
|---|---|---|---|
| T01 | 依赖检查 + lark-cli PATH 诊断脚本 | - | 容易 |
| T02 | FeishuClient 抽象接口定义 | - | 容易 |
| T03 | Pydantic 卡片/记录 schema | T02 | 容易 |
| T04 | 实现 LarkCLIClient.subprocess 封装 | T02 | 中等 |
| T05 | 实现重试 + 错误码识别 | T04 | 中等 |
| T06 | 实现 health_check（PATH/token/Base 存在） | T04 | 容易 |
| T07 | Base schema YAML 设计（4 张表字段） | - | 中等 |
| T08 | 实现 init_base（创建 Base + 表 + 字段） | T04,T07 | 困难 |
| T09 | 实现 send_card（单聊卡片推送） | T03,T05 | 中等 |
| T10 | 实现 batch_upsert（批量写入，≤200/批） | T05,T08 | 中等 |
| T11 | 实现 query_records + update_views | T10 | 中等 |
| T12 | 配置加载 + 环境变量校验 | T02 | 容易 |
| T13 | 单元 + 集成测试（覆盖率 > 80%） | T08-T11 | 中等 |

---

## 详细任务（精简）

### T01：依赖检查 + PATH 诊断
**AC：** 脚本能检测 lark-cli 是否安装、是否在 PATH、当前用户 token 是否有效。
**依赖：** 无

### T02：FeishuClient 抽象
**AC：** `from src.feishu import FeishuClient` 可用，含 6 个抽象方法。
**依赖：** 无

### T03：Pydantic 卡片/记录 schema
**AC：** `FeishuCard` / `BaseRecord` 模型；错误 JSON 抛 `ValidationError`。
**依赖：** T02

### T04：subprocess 封装
**AC：** `_run(cmd)` 返回 `CompletedProcess`；显式传 PATH 环境变量；超时 30s。
**依赖：** T02

### T05：重试 + 错误码
**AC：** 3 次重试指数退避；1254104 自动降批；91403 告警；1254064 抛 schema 错。
**依赖：** T04

### T06：health_check
**AC：** 返回 `{lark_cli: bool, token: bool, base: bool}`；任一 False 给出修复建议。
**依赖：** T04

### T07：Base schema YAML
**AC：** 4 个 YAML 文件（fund_pool/signals/arena/review）；字段含类型、公式、视图定义。
**依赖：** 无

### T08：init_base
**AC：**
- 检测 base_token 为空 → 创建新 Base
- 按 YAML 创建 4 张表 + 字段
- 创建 4 个视图（今日候选/观察池/信号/竞技场 Top-5）
- 写回 base_token/base_url 到 feishu.yaml
**依赖：** T04, T07

### T09：send_card
**AC：** 调 `lark-cli im +messages-send --msg-type interactive`；返回 message_id。
**依赖：** T03, T05

### T10：batch_upsert
**AC：**
- 单批 ≤ 200；超限自动分批
- 按 fund_code 主键 upsert（存在则更新）
- 批次间 0.5s 延迟
**依赖：** T05, T08

### T11：query_records + update_views
**AC：** 支持筛选条件；视图更新含筛选/排序/分组。
**依赖：** T10

### T12：配置加载
**AC：** 从 `config/feishu.yaml` 加载；环境变量 `${VAR}` 自动替换；缺 appId 抛异常。
**依赖：** T02

### T13：测试
**AC：** `pytest tests/feishu/` 全绿；覆盖率 > 80%；含烟雾测试脚本。
**依赖：** T08-T11

---

## 执行顺序
```
T01 → T02 → T03,T04,T07,T12
              ↓
        T05 → T06
              ↓
        T08 → T09 → T10 → T11
                          ↓
                        T13
```

关键路径：T01 → T02 → T04 → T08 → T10 → T13

---

## 变更记录
| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v0.1 | 2026-07-06 | tasks 初稿 | 小瑶 |
