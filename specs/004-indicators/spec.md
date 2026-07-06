# Feature #4 — indicators（基金分析指标层）

> **Spec-Kit specify 产出** | 来源：[PRD §6 F2-F5](../docs/prd.md) · [research.md §4](../docs/research.md)

---

## 1. Feature 简介

基于 data-provider 提供的原始数据，计算 4 层指标（L1 基本面 / L2 业绩 / L3 风格 / L4 现金流），作为筛选、分析、信号、竞技场的公共计算层。

---

## 2. 用户故事

- **作为系统**（下游模块），我需要一个统一的指标计算接口，输入基金代码 + 日期范围，输出全部 4 层指标
- **作为用户**，我希望每个指标都有"好/中/差"判断，便于理解

---

## 3. 输入 / 输出

### 输入
- 基金代码 + 日期范围
- 通过 DataProvider 拿原始数据（净值/持仓/经理/份额）

### 输出
```json
{
  "fund_code": "000001",
  "as_of_date": "2026-07-04",
  "L1_basic": {
    "scale": 27.30,
    "establish_years": 24.5,
    "manager_tenure_years": 3.2,
    "institution_holding_pct": 0.42,
    "management_fee": 0.015,
    "custodian_fee": 0.0025
  },
  "L2_performance": {
    "return_1y": 0.15, "return_3y": 0.08, "return_5y": 0.45,
    "rank_1y_percentile": 0.18,
    "max_drawdown": -0.18,
    "sharpe": 1.2,
    "volatility": 0.22,
    "alpha": 0.03, "beta": 1.05
  },
  "L3_style": {
    "style_box": "大盘成长",
    "industry_concentration_top3": 0.62,
    "holding_turnover": 1.35,
    "style_drift_score": 0.15
  },
  "L4_cashflow": {
    "share_change_yoy": 0.05,
    "institution_holding_change": -0.03,
    "dividend_count_5y": 4
  }
}
```

---

## 4. 功能需求（FR）

### FR-1：L1 基本面指标
- 规模、成立年限、经理任期、机构持有比例、费率
- 每个指标附"好/中/差"判断（按 research.md §4.1 阈值）

### FR-2：L2 业绩指标
- 收益率（1月/3月/6月/1年/3年/5年/成立以来）
- 同类排名百分位
- 最大回撤、夏普、波动率、阿尔法、贝塔
- 用 `empyrical` 计算风险指标

### FR-3：L3 风格分析
- 持仓风格（大/中/小盘 × 价值/平衡/成长），用九宫格分类
- 行业集中度（前 3 大行业占比）
- 持仓换手率
- 风格漂移检测（最近 4 季度风格变动频率）

### FR-4：L4 现金流
- 份额同比变动
- 机构持有比例变化（季度 diff）
- 历史分红次数

### FR-5：批量计算
- 输入基金列表，并行计算（用 `concurrent.futures`）
- 输出 DataFrame（一行一基金）

### FR-6：评级
- 综合 L1-L4 给出 5 星评级（参考晨星方法，简化版）

---

## 5. 非功能需求

| 维度 | 要求 |
|---|---|
| 性能 | 单基金全指标 ≤ 2s；批量 100 只 ≤ 30s |
| 可缓存 | 同日重复计算走缓存（SQLite） |
| 准确性 | 数值与 quantstats 交叉验证 |

---

## 6. 验收标准（AC）

### AC-1：单基金全指标
**Given** 基金 000001 + 近 5 年数据
**When** 调用 `calc_all("000001", start, end)`
**Then**
1. 返回 L1-L4 全部字段
2. 每个字段有数值
3. 附"好/中/差"标签

### AC-2：批量并行
**Given** 100 只基金
**When** 调用 `calc_batch(codes)`
**Then**
1. 耗时 ≤ 30s
2. 返回 DataFrame，100 行

### AC-3：数值准确
**Given** 同一基金
**When** 用 quantstats 独立计算
**Then** 夏普/回撤差异 < 0.01

### AC-4：缓存命中
**Given** 同日已计算过
**When** 再次调用
**Then** 走缓存，无重复计算

---

## 7. 显式不做
- ❌ 不做实时指标（基于日频）
- ❌ 不做债券/货币基金指标
- ❌ 不做自定义因子（MVP 用标准指标）

---

## 8. 依赖
- 前置：#1 data-provider
- 下游：#5 fund-screener / #6 fund-analyzer / #7 signal-engine / #8 strategy-arena

---

## 9. 开放问题
1. 风格九宫格分类阈值如何确定（大/中/小盘分界）？
2. 评级算法用加权平均还是规则评级？
3. 缓存粒度是按基金还是按指标？

---

## 变更记录
| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v0.1 | 2026-07-06 | specify 初稿 | 小瑶 |
