# Feature #10 — mac-frontend 实施计划

> 含 5 要素

---

## 1. 技术选型

| 库 / 工具 | 版本 | 用途 | 理由 |
|---|---|---|---|
| `next` | ≥14.2 | 框架 | App Router（稳定） |
| `react` / `react-dom` | ≥18.3 | UI 库 | Next 内置 |
| `typescript` | ≥5.4 | 类型 | 全链路类型安全 |
| `tailwindcss` | ≥3.4 | 样式 | 现代 SaaS 风首选 |
| `shadcn/ui` | latest | 组件库 | 基于 Radix，可定制，类 Linear 风 |
| `tanstack/react-query` | ≥5.40 | 数据请求 | 缓存/重试/乐观更新 |
| `openapi-typescript` | ≥7.0 | 类型生成 | 从 OpenAPI 生成 TS 类型 |
| `echarts-for-react` | ≥3.0 | 图表 | 金融图表性能强（大数据优化） |
| `react-hook-form` + `zod` | latest | 表单 | YAML 规则表单化 |
| `lucide-react` | latest | 图标 | shadcn 标配 |
| `sonner` | latest | Toast | shadcn 推荐 |
| `pnpm` | ≥9 | 包管理 | 快 + 节省磁盘 |

**不引入**：Redux（TanStack Query 够用）、Material-UI（视觉不符）、D3（学习成本高）。

---

## 2. 数据模型（前端状态）

### TanStack Query 缓存 key 约定
```typescript
// 示例
const fundsListKey = ['funds', { category, domain, page }];
const fundDetailKey = ['funds', code];
const strategyListKey = ['strategies', { domain, sort }];
const strategyTimeseriesKey = ['strategies', id, 'timeseries', { period }];
```

### 核心 TS 类型（OpenAPI 自动生成）
```typescript
// frontend/types/api.ts（自动生成，勿手改）
import type { paths } from "./api-schema";
type Fund = paths['/api/funds/{code}']['get']['responses']['200']['content']['application/json'];
type Strategy = paths['/api/strategies/{id}']['get']['responses']['200']['content']['application/json'];
// ...
```

---

## 3. 接口契约

### 前端 → API
统一通过 `frontend/lib/api.ts` 的 fetch 封装：
```typescript
// frontend/lib/api.ts
const BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new ApiError(await res.json());
  return res.json();
}
// apiPost / apiPut / apiDelete 同理
```

### 各页面数据契约
见 [specs/011-api-backend/spec.md](../011-api-backend/spec.md) FR-1 ~ FR-7。

---

## 4. 依赖列表

- 上游：#11 api-backend（提供 REST API + OpenAPI）
- 模块内：无
- 下游：无

---

## 5. 测试策略

| 层级 | 工具 | 覆盖点 |
|---|---|---|
| 单元 | vitest + React Testing Library | 组件渲染、交互 |
| 集成 | vitest + msw（mock API） | 页面端到端 |
| E2E（可选） | Playwright | 关键流程 |
| 类型 | tsc --noEmit | 类型安全 |
| 视觉 | Storybook（可选） | 组件展示 |

覆盖率 > 75%。

---

## 6. 关键决策（小 ADR）

### 为什么选 ECharts 而不是 Recharts
- 周期分析含 5 年日频数据（~1200 点），ECharts 大数据优化（dataSampling）性能强
- 回撤阴影 + 基准对比 = 组合图，ECharts 配置灵活
- Recharts 在大数据下卡顿明显

### 为什么选 shadcn/ui 而不是 Ant Design
- 视觉更接近 Linear/Notion（现代 SaaS 风）
- 基于 Radix，可定制性强
- 不依赖全局 CSS

### 为什么 App Router 而不是 Pages Router
- App Router 是 Next 14 稳定推荐
- Layouts/Loading/Error 边界原生支持
- Server Components（虽然本项目主要 CSR，但保留扩展空间）

### 为什么 TanStack Query 而不是 SWR
- 乐观更新支持更完善（加观察池/采用策略场景）
- DevTools 调试友好

---

## 7. 目录结构

```
frontend/
├── app/                      # Next.js App Router
│   ├── layout.tsx            # 根布局
│   ├── page.tsx              # 首页 Dashboard
│   ├── strategies/
│   │   ├── page.tsx          # 策略池总览
│   │   └── [id]/
│   │       └── page.tsx      # 策略详情 + 周期分析
│   ├── funds/
│   │   └── [code]/
│   │       └── page.tsx      # 单基金深度解读
│   ├── discover/
│   │   └── page.tsx          # 发现 / 推荐
│   └── manage/
│       ├── page.tsx          # 管理台首页
│       ├── config/
│       ├── observation/
│       └── jobs/
├── components/
│   ├── ui/                   # shadcn 组件
│   ├── charts/               # ECharts 封装
│   │   ├── PeriodReturnChart.tsx
│   │   ├── NavCurveChart.tsx
│   │   └── CashflowChart.tsx
│   ├── fund/                 # 单基金页模块
│   └── strategy/             # 策略页模块
├── lib/
│   ├── api.ts                # fetch 封装
│   ├── query-keys.ts         # TanStack Query keys
│   └── utils.ts
├── types/
│   └── api.ts                # openapi-typescript 生成（勿手改）
├── package.json
├── tsconfig.json
├── tailwind.config.ts
└── next.config.js
```

---

## 8. 视觉设计规范

### 配色（现代 SaaS 风）
| 用途 | 颜色 |
|---|---|
| 主色 | `oklch(0.55 0.2 250)` 类 Linear 蓝 |
| 背景 | `#FAFAFA` |
| 卡片 | `#FFFFFF` + 边框 `#E5E5E5` |
| 正收益 | `#10B981` 绿（A 股惯例） |
| 负收益 | `#EF4444` 红 |
| 加仓信号 | 绿 |
| 减仓信号 | 红 |
| 止损信号 | 橙 `#F59E0B` |

### 字体
- 默认：Inter（英文）+ 系统中文字体
- 数字：Tabular Nums（等宽数字）

### 间距与圆角
- 卡片圆角：`rounded-lg`（8px）
- 按钮圆角：`rounded-md`（6px）
- 间距：Tailwind 4/8/12/16 系统

---

## 变更记录

| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v0.1 | 2026-07-06 | plan 初稿 | 小瑶 |
