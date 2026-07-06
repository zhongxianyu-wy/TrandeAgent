# Step 6 — 飞书 CLI 接入调研补充报告

> **本文件是 Step 6 产出**，基于实际源码阅读与本机环境验证。
> 修正 research.md §2 的部分假设，并据此更新 Feature #2 feishu-io 的 spec。

---

## 1. 关键事实校正

### research.md §2 的原结论（subagent 报告）
> "lark-cli 真实存在（npm 包 `@larksuite/cli`，GitHub `larksuite/cli`，本机已装 skills）"

### 实际验证结果（2026-07-06）

| 验证项 | 结果 | 证据 |
|---|---|---|
| `@larksuite/cli` npm 包 | ✅ 真实存在 | `npm view @larksuite/cli version` → `1.0.65` |
| GitHub `larksuite/cli` | ✅ 真实存在（由 npm 包反向证明） | npm view 返回版本号 |
| 本机 skills 文档 | ✅ 真实存在 | `~/.trae-cn/skills/lark-shared/SKILL.md` 可读，5833 字节 |
| **lark-cli 二进制** | ❌ **未安装** | `which lark-cli` → not found |

**结论：** skills 文档（说明书）先于二进制安装在 Trae 平台上，但运行 lark-cli 命令前必须先安装 `@larksuite/cli` 二进制。

---

## 2. 从源码确认的关键信息（SKILL.md 原文）

来源：`~/.trae-cn/skills/lark-shared/SKILL.md`

### 2.1 配置初始化
```bash
lark-cli config init --new
```
- 阻塞式，等待用户打开授权链接完成
- Agent 应 background 方式运行，提取链接发给用户

### 2.2 身份与认证
- **Bot 身份**：`--as bot`，只需 appId + appSecret，自动获取 tenant_access_token
- **User 身份**：`--as user`，需 `lark-cli auth login` 用户授权
- **关键规则**：`auth login` 必须指定 `--scope` 或 `--domain`，scope 增量累积

### 2.3 权限不足处理
- 错误响应含 `permission_violations`、`console_url`、`hint`
- Bot 缺权限 → 引导用户去后台开通
- User 缺权限 → `lark-cli auth login --scope "<missing>"`

### 2.4 更新机制
- 命令执行后 JSON 含 `_notice.update` 字段
- 更新命令：`npm update -g @larksuite/cli && npx skills add larksuite/cli -g -y`

### 2.5 安全规则（必须遵守）
- ❌ **禁止输出密钥明文**（appSecret、accessToken）
- ✅ 写/删操作前必须确认用户意图
- ✅ 用 `--dry-run` 预览危险请求

### 2.6 高风险操作门禁（exit code 10）
- 高风险写操作（如 `drive +delete`）未带 `--yes` → exit 10
- stderr 返回结构化 envelope：
  ```json
  {"ok": false, "error": {"type": "confirmation_required", "risk": {"level": "high-risk-write"}}}
  ```
- **绝对禁止**：看到 exit 10 自动加 `--yes`（等于禁用门禁）
- **正确做法**：向用户确认 → 用户同意 → argv 末尾追加 `--yes` 重试

---

## 3. 对 Feature #2 feishu-io Spec 的影响

### 3.1 必须补充的前置条件

**feishu-io spec.md §4 FR-5 原文：**
> 首次运行 `lark-cli config init` 引导用户配置 appId/appSecret

**需要补充：**
1. **lark-cli 二进制安装**（首次必做，不在 PATH）：
   ```bash
   npm install -g @larksuite/cli
   ```
2. **配置初始化必须 background 模式**：`lark-cli config init --new` 会阻塞等待用户授权，Agent 不能 foreground 调用
3. **禁止输出 appSecret 明文**：日志/异常处理必须脱敏
4. **高风险操作门禁**：Base 写入可能触发 exit 10（虽然 batch_create 风险较低，但删除/更新需 `--yes`）

### 3.2 需要新增的 FR

**新增 FR-7：lark-cli 安装与版本管理**
- 首次运行检测 `which lark-cli`，未安装则提示安装命令
- 提供 `feishu install-cli` 命令一键安装
- 监测 `_notice.update` 字段，提示用户更新

**新增 FR-8：安全规则**
- 日志中 appSecret/accessToken 必须脱敏（`***` 替换）
- 删除/批量更新操作必须经用户确认（exit 10 处理）
- 提供统一的安全 `call_lark_cli(cmd, confirm=False)` 封装

### 3.3 实现细节修正

**plan.md §3.2 `LarkCLIClient` 实现要点：**
- 增加依赖检查：构造时 `shutil.which("lark-cli")`，不存在抛 `LarkCLINotInstalled`
- `_run()` 返回处理：检查 exit code 10 → 解析 stderr envelope → 抛 `ConfirmationRequired` 异常
- `_run()` 输出解析：检测 `_notice.update` 字段，写入日志提示用户更新
- 日志脱敏：所有 cmd 参数中的 `--app-secret` 值替换为 `***`

---

## 4. 对 Feature #2 tasks 的影响

需要在 tasks.md 增加一项 T00（前置）：
- **T00：lark-cli 安装与依赖检查脚本**（新增）
  - 实现 `feishu install-cli` 命令
  - 启动时检测 `which lark-cli`
  - 检测到未安装时给出明确安装指引

原 T01 "依赖检查 + PATH 诊断" 升级，包含 lark-cli 二进制检测。

---

## 5. 推荐的安装与初始化流程（最终方案）

```bash
# Step 1: 安装 lark-cli 二进制
npm install -g @larksuite/cli

# Step 2: 验证安装
lark-cli --version  # 应输出 1.0.65 或更高

# Step 3: 配置应用（background 模式，等待用户授权）
lark-cli config init --new
# 系统输出授权链接，用户在浏览器完成操作

# Step 4: 用户身份授权（操作 Base 需要 user 身份）
lark-cli auth login --scope "base:app"  # 或具体 scope

# Step 5: 验证可用
python -m src.feishu health
```

---

## 6. 对其他 Feature 的影响

| Feature | 影响 |
|---|---|
| #1 data-provider | 无（不依赖飞书） |
| #2 feishu-io | **直接影响**，spec/plan/tasks 需更新（见 §3-4） |
| #3 scheduler | 无直接影响，但 launchd plist 的 PATH 必须含 npm global bin（`/opt/homebrew/bin` 或 `/usr/local/bin`） |
| #4-#9 | 无直接影响 |

---

## 7. PRD 是否需要更新？

**结论：PRD 不需要修改**，理由：
- PRD §6 F6/F7 描述的是"做什么"，不涉及"如何安装 lark-cli"
- lark-cli 安装是实施层细节，归 plan/tasks
- 但 PRD §12 风险表可补一条："lark-cli 二进制需手动安装，首次部署门槛"

---

## 8. 引用

- 本机源码：`/Users/zhongxianyu/.trae-cn/skills/lark-shared/SKILL.md`（5833 字节，可读）
- npm 包验证：`npm view @larksuite/cli version` → `1.0.65`
- 二进制状态：`which lark-cli` → not found（需安装）

---

## 变更记录
| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v0.1 | 2026-07-06 | Step 6 调研补充报告 | 小瑶 |
