# Feature #3 — scheduler（定时调度）

> **Spec-Kit specify 产出** | 来源：[PRD §6 F9](../docs/prd.md)

---

## 1. Feature 简介

提供基于 macOS launchd 的定时调度，每个交易日 16:00（可配置）触发主流程；过滤非交易日；启动时检测漏推送窗口并补发。

---

## 2. 用户故事

- **作为用户**，我希望每个交易日 16:00 自动收到推送，周末/节假日不发
- **作为用户**，我希望 Mac 关机后重启时，漏掉的推送能补发

---

## 3. 输入 / 输出

- 输入：launchd plist + 主流程入口
- 输出：每日按时触发 + 漏推送补发

---

## 4. 功能需求（FR）

### FR-1：launchd 定时
- 安装 `~/Library/LaunchAgents/com.trandeagent.daily.plist`
- `StartCalendarInterval` 设为 16:00（可配置）
- 触发 `python -m src.main daily`

### FR-2：交易日过滤
- 用 `chinese_calendar` 库判定 A 股交易日
- 非交易日直接 return，不发推送

### FR-3：漏推送检测与补发
- 启动时读 `data/state/last_run.json` 上次运行时间
- 若距上次运行 > 1 个交易日，补发漏掉的"每日报告"（用历史数据生成）
- 补发上限：5 个交易日（更早的不补）

### FR-4：手动触发
- `python -m src.main daily --force`：强制运行（忽略交易日）
- `python -m src.main daily --dry-run`：模拟运行不推送

### FR-5：运行状态记录
- 每次运行写入 `data/state/run_history.jsonl`
- 字段：run_at, status, duration_sec, fund_count, error

---

## 5. 非功能需求

| 维度 | 要求 |
|---|---|
| 准时性 | 16:00 ±5 分钟内触发 |
| 可靠性 | launchd 失败时写日志 |
| 可观测 | 每次运行记录历史 |
| macOS 兼容 | launchd plist 显式 PATH |

---

## 6. 验收标准（AC）

### AC-1：按时触发
**Given** 交易日 16:00
**When** launchd 触发
**Then** 主流程启动，30 分钟内完成

### AC-2：节假日不发
**Given** 国庆节 10/1
**When** launchd 触发
**Then** chinese_calendar 判定非交易日，return

### AC-3：漏推送补发
**Given** 上次运行 3 个交易日前
**When** 主流程启动
**Then**
1. 检测漏 2 个交易日
2. 用历史数据补发 2 条"每日报告"
3. 写入 run_history

### AC-4：手动强制
**Given** 周末
**When** `python -m src.main daily --force`
**Then** 强制运行

### AC-5：launchd plist 安装
**Given** `scripts/install_launchd.sh`
**When** 执行
**Then**
1. plist 安装到 `~/Library/LaunchAgents/`
2. 显式 PATH 含 python/lark-cli 路径
3. `launchctl list | grep trandeagent` 可见

---

## 7. 显式不做
- ❌ 不做云定时（迁云时替换）
- ❌ 不做实时盘中触发（仅日频）
- ❌ 不做多时段推送（仅 16:00）

---

## 8. 依赖关系
- 无前置依赖
- 下游：所有业务模块（通过 main.py）

---

## 9. 开放问题
1. 补发推送是否需要标注"补发"标识？
2. launchd plist 是否支持用户配置触发时间（非 16:00）？

---

## 变更记录
| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v0.1 | 2026-07-06 | specify 初稿 | 小瑶 |
