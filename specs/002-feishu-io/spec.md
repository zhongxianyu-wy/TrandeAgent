# Feature #2 — feishu-io（飞书 IO 层）

> **Spec-Kit specify 产出** | Step 5.3 第①步
> 来源：[PRD §6 F6, F7](../docs/prd.md) · [research.md §2](../docs/research.md)

---

## 1. Feature 简介

封装飞书侧所有 IO（单聊卡片推送 + 多维表格读写），对下游业务模块提供统一 `FeishuClient` 接口，隐藏 lark-cli subprocess 调用细节、token 管理、错误码处理、QPS 限流。

---

## 2. 用户故事

- **作为系统**（下游模块），我需要一个统一的飞书 IO 接口，不必关心 lark-cli 命令细节
- **作为用户**，我希望每日 16:00 收到一张结构化卡片，可点击跳转 Base
- **作为用户**，我希望所有基金数据写入飞书 Base 多张表，便于可视化查看

---

## 3. 输入 / 输出契约

### 输入
- 卡片 JSON（来自 reporter 模块）或 Base 记录（来自业务模块）
- 身份：`bot`（推送消息）/ `user`（操作 Base）

### 输出
- 推送：`message_id` 或失败原因
- Base 写入：`record_ids` 列表

---

## 4. 功能需求（FR）

### FR-1：单聊卡片推送
- 通过 `lark-cli im +messages-send --msg-type interactive --as bot` 推送
- 推送目标：当前用户的 open_id（配置文件）
- 卡片 JSON 必须通过 schema 校验
- 推送失败重试 3 次

### FR-2：多维表格初始化
- 首次运行检测 Base 是否存在，不存在则创建
- 创建 4 张数据表：基金池 / 信号 / 策略竞技场 / 复盘
- 创建字段（含类型、公式、视图）

### FR-3：多维表格批量写入
- 单批 ≤ 200 条（API 限制）
- 支持单表批量 upsert（按 fund_code 去重）
- 连续写同一表须串行，批次间延迟 0.5s

### FR-4：多维表格视图管理
- 创建视图：今日候选 / 观察池 / 信号 / 竞技场 Top-5
- 配置筛选、排序、分组

### FR-5：身份与鉴权
- 首次运行 `lark-cli config init` 引导用户配置 appId/appSecret
- `lark-cli auth login --scope ...` 引导用户授权
- Token 自动刷新（lark-cli 管理）

### FR-6：限流与错误处理
- 单聊推送 QPS ≤ 5（远超需求，实际每日 1 条）
- Base 写入串行，批次间 0.5s
- 错误码识别（1254104 超限、91403 无权限、1254064 日期格式错）

---

## 5. 非功能需求（NFR）

| 维度 | 要求 |
|---|---|
| 性能 | 单条推送 ≤ 5s；Base 批量写 200 条 ≤ 10s |
| 可靠性 | 推送失败重试 3 次；Base 写入失败不阻塞推送 |
| 可观测 | 每次操作记录日志（lark-cli stdout/stderr） |
| 安全 | appId/appSecret 用环境变量，不写代码 |
| 个人单用户 | 不做多租户 |

---

## 6. 验收标准（AC）

### AC-1：首次初始化
**Given** 飞书应用已创建但 Base 不存在
**When** 触发 `feishu init`
**Then**
1. 自动创建一个 Base
2. 创建 4 张表 + 字段 + 视图
3. 输出 Base URL

### AC-2：单聊推送
**Given** 卡片 JSON
**When** 调用 `send_card(card_json)`
**Then**
1. 用户飞书单聊收到卡片
2. 卡片可点击跳转 Base
3. 返回 `message_id`

### AC-3：Base 批量写入
**Given** 50 条基金记录
**When** 调用 `batch_upsert("基金池", records)`
**Then**
1. 全部写入成功
2. 耗时 ≤ 10s
3. 重复 fund_code 更新而非新增

### AC-4：失败重试
**Given** 网络抖动
**When** 推送失败
**Then**
1. 重试 3 次（指数退避）
2. 全部失败后写错误日志 + 告警
3. Base 写入失败不阻塞推送

### AC-5：配置引导
**Given** 首次运行未配置
**When** 调用任何方法
**Then**
1. 抛 `FeishuNotConfigured` 异常
2. 提示运行 `lark-cli config init`

---

## 7. 边界与显式不做

- ❌ 不做群聊推送（MVP 仅单聊）
- ❌ 不做接收消息（Roadmap，对应 US 单聊交互）
- ❌ 不做多用户（个人单租户）
- ❌ 不做飞书云文档（Roadmap）
- ❌ 不做 webhook 自定义机器人（仅应用机器人）

---

## 8. 数据样例

### 卡片 JSON 片段
```json
{
  "header": {"template": "blue", "title": {"content": "📊 TrandeAgent 每日报告"}},
  "elements": [
    {"tag": "markdown", "content": "**组合表现**: +0.85%"},
    {"tag": "action", "actions": [
      {"tag": "button", "text": {"content": "查看详情"},
       "type": "primary", "open_url": "https://feishu.cn/base/xxx"}
    ]}
  ]
}
```

### Base "基金池" 表字段
| 字段名 | 类型 | 说明 |
|---|---|---|
| fund_code | 文本 | 主键 |
| fund_name | 文本 |  |
| fund_type | 单选 | qdii/index/etf_link/active_stock |
| scale | 数字 | 亿 |
| sharpe | 数字 | 保留 2 位 |
| max_drawdown | 数字 | 百分比 |
| reason | 文本 | 选中理由 |
| is_observation | 复选框 |  |

---

## 9. 依赖关系
- **本 feature 无前置依赖**（基础设施层）
- 下游：所有需要推送或写 Base 的模块

---

## 10. 开放问题（clarify）
1. 首次初始化 Base 时，字段公式（如综合得分）如何定义？
2. 推送失败后除了日志，是否需要邮件/系统通知？
3. Base URL 是否需要写入本地配置供后续直接复用？

---

## 变更记录
| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v0.1 | 2026-07-06 | specify 初稿 | 小瑶 |
