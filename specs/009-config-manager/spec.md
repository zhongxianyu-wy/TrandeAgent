# Feature #9 — config-manager（YAML 策略配置）

> 来源：[PRD §6 F8](../docs/prd.md) · [context.md US-5](../docs/context.md)

---

## 1. Feature 简介

集中管理用户策略规则（筛选/择时/竞技场），提供 YAML schema 校验、配置变更影响范围检测、Git 版本管理。

---

## 2. 用户故事

- **作为用户**，我希望把所有规则集中到一个 YAML，Git 版本管理，能随时回滚
- **作为用户**，我希望改配置后系统提示"本次修改影响 N 只基金"

---

## 3. 输入 / 输出
- 输入：用户编辑的 YAML
- 输出：校验结果 + 影响范围报告

---

## 4. 功能需求（FR）

### FR-1：配置 schema 校验
- 用 Pydantic 校验：strategies / signals / arena 三大配置块
- 错误时抛详细 ValidationError + 行号

### FR-2：影响范围检测
- 改筛选规则 → 计算影响多少基金进出候选池
- 改信号规则 → 计算多少观察池基金信号会变
- 改竞技场配置 → 提示需要重跑回测

### FR-3：版本管理
- 每次保存自动 `git commit -am "config: <change>"`
- 提供 `config diff` / `config rollback <commit>` 命令

### FR-4：环境变量替换
- 支持 `${VAR}` 引用环境变量（如 LLM API Key）

### FR-5：默认值与样例
- 首次运行生成 `config/strategies.yaml.example`

---

## 5. 非功能需求
- 校验 < 1s
- 影响范围检测 < 5s（依赖 #4/#5/#7）

---

## 6. 验收标准（AC）

### AC-1：schema 校验
**Given** 错误 YAML
**When** 加载
**Then** 抛 ValidationError + 行号

### AC-2：影响范围
**Given** 改筛选规则（规模 2-50 → 2-100）
**When** 检测影响
**Then**
1. 输出"本次修改影响 +N 只基金进 / -M 只基金出"
2. 列出新增/移除基金代码

### AC-3：版本管理
**Given** 多次保存
**When** `config log`
**Then** 输出 commit 历史

### AC-4：回滚
**Given** 当前配置出错
**When** `config rollback HEAD~1`
**Then** 恢复到上一个版本

---

## 7. 显式不做
- ❌ 不做 Web UI（MVP CLI）
- ❌ 不做多 profile（单用户）

---

## 8. 依赖
- 前置：#5 fund-screener, #7 signal-engine（用于影响范围检测）
- 下游：所有模块（都用配置）

---

## 9. 开放问题
1. 影响范围检测是同步还是异步（耗时大时）？
2. 是否需要配置导入/导出？

---

## 变更记录
| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v0.1 | 2026-07-06 | specify 初稿 | 小瑶 |
