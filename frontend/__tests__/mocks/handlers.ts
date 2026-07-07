/**
 * T18: MSW 默认 handlers，覆盖所有后端端点的 mock 响应。
 * 所有响应遵循 { code, message, data } 包装。
 */
import { http, HttpResponse } from "msw";

const ok = <T>(data: T) =>
  HttpResponse.json({ code: 0, message: "ok", data });

export const handlers = [
  // 系统
  http.get("*/api/system/status", () =>
    ok({
      data_freshness: { total: 1200, stale: 3 },
      last_run: "2026-07-07",
      active_jobs: 1,
      observation_pool_size: 5,
      strategy_count: 48,
    }),
  ),
  http.get("*/api/system/health", () =>
    ok({ status: "ok", version: "1.0" }),
  ),

  // 基金
  http.get("*/api/funds", ({ request }) => {
    const url = new URL(request.url);
    const size = Number(url.searchParams.get("size") || 20);
    const items = Array.from({ length: Math.min(size, 3) }).map((_, i) => ({
      fund_code: `00000${i + 1}`,
      fund_name: `测试基金${i + 1}`,
      fund_category: "混合",
      fund_type: "开放式",
      latest_scale: 1.2e8,
      rating: 4,
      return_1y: 0.12 + i * 0.01,
    }));
    return ok({ items, page: 1, size, total: items.length });
  }),
  http.get("*/api/funds/:code", ({ params }) =>
    ok({
      fund_code: params.code as string,
      fund_name: "测试基金",
      fund_type: "开放式",
      fund_category: "混合",
      manager_names: "张三",
      establish_date: "2018-01-01",
      latest_scale: 1.5e8,
      management_fee: 0.015,
      custodian_fee: 0.0025,
      history_months: 90,
      indicators: {
        rating: 4,
        l2_performance: {
          return_1y: 0.18,
          sharpe: 1.2,
          max_drawdown: -0.15,
          volatility: 0.2,
        },
      },
    }),
  ),
  http.get("*/api/funds/:code/nav", () =>
    ok({
      items: [
        { trade_date: "2026-07-01", unit_nav: 1.5, accum_nav: 2.0, daily_return: 0.01 },
      ],
      page: 1,
      size: 250,
      total: 1,
    }),
  ),
  http.get("*/api/funds/:code/holdings", () =>
    ok({
      fund_code: "000001",
      industries: [
        { industry: "科技", weight: 0.35 },
        { industry: "消费", weight: 0.25 },
        { industry: "金融", weight: 0.2 },
        { industry: "医药", weight: 0.1 },
      ],
      manager_profile: {
        name: "张三",
        tenure_years: 5.5,
        history: [
          { period: "2018-2024", fund: "测试基金", scale: 2e8, return: 0.18 },
        ],
      },
    }),
  ),
  http.get("*/api/funds/:code/cashflow", () =>
    ok({
      fund_code: "000001",
      dates: ["2026-Q1", "2026-Q2"],
      share_change: [1e7, -5e6],
      institution_holding: [12.5, 13.0],
    }),
  ),
  http.get("*/api/funds/:code/report", () =>
    ok({
      fund_code: "000001",
      markdown:
        "## 投资综述\n该基金表现稳健，**近一年收益 18%**。\n\n## 关键点\n- 夏普比率优秀\n- 依据【夏普优势】",
      references: [{ label: "夏普优势" }],
      json: { score: 85 },
    }),
  ),
  http.post("*/api/funds/:code/analyze", () =>
    ok({ job_id: "job-analyze-12345678" }),
  ),

  // 策略
  http.get("*/api/strategies", ({ request }) => {
    const url = new URL(request.url);
    const domain = url.searchParams.get("domain") || "价值";
    const items = Array.from({ length: 3 }).map((_, i) => ({
      strategy_id: `strat-${domain}-${i + 1}`,
      prototype_id: "quality",
      domain,
      rank_in_domain: i + 1,
      composite_score: 85 - i * 5,
      annual_return: 0.15 - i * 0.02,
      sharpe: 1.3 - i * 0.1,
      max_drawdown: -0.12 + i * 0.01,
      adopted: i === 0,
      disabled: false,
    }));
    return ok({ items, page: 1, size: 100, total: items.length });
  }),
  http.get("*/api/strategies/:id", ({ params }) =>
    ok({
      strategy_id: params.id as string,
      prototype_id: "quality",
      prototype_name: "质量价值",
      domain: "价值",
      mind_model: "低估值+高ROE",
      param_diff: "N=20",
      adopted: false,
      disabled: false,
      composite_score: 88,
      annual_return: 0.18,
      sharpe: 1.4,
      max_drawdown: -0.1,
    }),
  ),
  http.get("*/api/strategies/:id/timeseries", () =>
    ok({
      period: "monthly",
      labels: ["2026-01", "2026-02", "2026-03"],
      returns: [0.03, -0.02, 0.05],
      benchmark_returns: [0.02, -0.01, 0.03],
    }),
  ),
  http.get("*/api/strategies/:id/nav", () =>
    ok({
      dates: ["2026-01-01", "2026-02-01", "2026-03-01"],
      nav: [1.0, 1.03, 1.01],
      drawdown: [0, -0.01, -0.005],
      benchmark_nav: [1.0, 1.02, 1.01],
    }),
  ),
  http.get("*/api/strategies/:id/cashflow", () =>
    ok({
      dates: ["2026-Q1", "2026-Q2"],
      share_change: [1e6, 2e6],
      institution_holding: [10, 12],
    }),
  ),
  http.post("*/api/strategies/:id/adopt", ({ params }) =>
    ok({ strategy_id: params.id, adopted: true }),
  ),
  http.post("*/api/strategies/:id/disable", ({ params }) =>
    ok({ strategy_id: params.id, disabled: true }),
  ),

  // 发现
  http.get("*/api/discover", () => {
    const domains: Record<string, string[]> = {
      价值: ["000001", "000002"],
      成长: ["000003"],
      红利: ["000004"],
      趋势: ["000005"],
      逆向: [],
      全球配置: [],
      指数增强: [],
      低波: [],
    };
    return ok({ domains, window: "today" });
  }),
  http.get("*/api/discover/reasons/:code", ({ params }) =>
    ok({
      fund_code: params.code as string,
      reasons: ["评级 4 星", "夏普 1.2"],
    }),
  ),

  // 观察池
  http.get("*/api/observation", () => ok({ pool: ["000001", "000002"] })),
  http.post("*/api/observation/:code", ({ params }) =>
    ok({ code: params.code, in_pool: true }),
  ),
  http.delete("*/api/observation/:code", ({ params }) =>
    ok({ code: params.code, in_pool: false }),
  ),
  http.get("*/api/observation/:code/signals", () =>
    ok([
      { fund_code: "000001", signal_type: "add", date: "2026-07-01", strength: 0.8 },
    ]),
  ),

  // 配置
  http.get("*/api/config", () =>
    ok({
      observation_pool: ["000001"],
      signal_rules: [{ type: "ma_cross", fast: 5, slow: 20 }],
    }),
  ),
  http.put("*/api/config", () =>
    ok({
      impacts: [
        { field: "observation_pool", affected_funds: ["000002", "000003"] },
      ],
      affected_count: 2,
    }),
  ),
  http.get("*/api/config/history", () =>
    ok({
      history: [
        { commit: "abc1234567", date: "2026-07-06", message: "init" },
      ],
    }),
  ),

  // 任务
  http.get("*/api/jobs", () =>
    ok({
      items: [
        {
          job_id: "job-1",
          type: "refresh-data",
          status: "succeeded",
          progress: 1,
          started_at: "2026-07-07T10:00:00",
          finished_at: "2026-07-07T10:05:00",
        },
      ],
    }),
  ),
  http.post("*/api/jobs/refresh-data", () =>
    ok({ job_id: "job-refresh-12345678" }),
  ),
  http.post("*/api/jobs/backtest", () => ok({ job_id: "job-back-12345678" })),
];
