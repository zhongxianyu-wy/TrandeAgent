/**
 * T02: API 类型定义。
 *
 * 说明：后端 OpenAPI 的 data 字段是泛型 anyOf（无具体 schema），
 * 因此 openapi-typescript 生成的类型对业务无指导意义。
 * 这里基于 src/api/schema.py 手工维护业务类型（与后端 Pydantic 模型对齐），
 * 保持单一数据源、便于前后端联调。
 *
 * 不要手改后端 Pydantic 模型，如需新增字段请同步本文件。
 */

// ---------------------------------------------------------------------------
// 统一响应包装
// ---------------------------------------------------------------------------
/** 统一成功响应：{ code, message, data } */
export interface ApiResponse<T = unknown> {
  code: number;
  message: string;
  data: T;
}

/** 统一错误响应 */
export interface ErrorResponse {
  code: number;
  message: string;
  detail?: Record<string, unknown> | null;
}

/** 分页数据 */
export interface PaginatedData<T = unknown> {
  items: T[];
  page: number;
  size: number;
  total: number;
}

// ---------------------------------------------------------------------------
// 任务
// ---------------------------------------------------------------------------
export type JobStatus = "pending" | "running" | "succeeded" | "failed";

export interface Job {
  job_id: string;
  type: string; // refresh-data | backtest | analyze | regenerate
  status: JobStatus;
  progress: number; // 0-1
  started_at: string;
  finished_at?: string | null;
  result?: Record<string, unknown> | null;
  error?: string | null;
}

// ---------------------------------------------------------------------------
// 周期分析 / 净值曲线
// ---------------------------------------------------------------------------
export type Period = "daily" | "weekly" | "monthly" | "quarterly" | "yearly";

/** 多周期收益率（柱状图） */
export interface PeriodReturn {
  period: Period;
  labels: string[];
  returns: number[];
  benchmark_returns: number[];
}

/** 净值曲线 + 回撤 + 基准 */
export interface NavCurve {
  dates: string[];
  nav: number[];
  drawdown: number[]; // 负数
  benchmark_nav: number[];
}

// ---------------------------------------------------------------------------
// 基金
// ---------------------------------------------------------------------------
export interface FundBasicInfo {
  fund_code: string;
  fund_name: string;
  fund_type: string;
  fund_category: string;
  manager_names: string;
  establish_date: string;
  latest_scale?: number | null;
  management_fee?: number | null;
  custodian_fee?: number | null;
  history_months?: number | null;
}

export interface FundListItem {
  fund_code: string;
  fund_name: string;
  fund_category: string;
  fund_type: string;
  latest_scale?: number | null;
  rating: number;
  return_1y?: number | null;
}

export interface NavPoint {
  trade_date: string;
  unit_nav?: number | null;
  accum_nav?: number | null;
  daily_return?: number | null;
}

/** 单基金详情（含 L1-L4 指标，业务层返回字典） */
export interface FundDetail extends FundBasicInfo {
  indicators?: FundIndicators;
  [key: string]: unknown;
}

/** 基金指标（L1-L4，字段较宽松，业务可能返回部分） */
export interface FundIndicators {
  rating?: number;
  l1_basic?: Record<string, number | null>;
  l2_performance?: {
    return_1m?: number | null;
    return_3m?: number | null;
    return_1y?: number | null;
    return_3y?: number | null;
    sharpe?: number | null;
    max_drawdown?: number | null;
    volatility?: number | null;
    [key: string]: number | null | undefined;
  };
  l3_style?: Record<string, number | null>;
  l4_cashflow?: Record<string, unknown>;
  [key: string]: unknown;
}

/** 持仓明细 */
export interface Holdings {
  fund_code: string;
  stocks?: Array<{
    stock_name: string;
    stock_code?: string;
    weight?: number;
    industry?: string;
    [key: string]: unknown;
  }>;
  industries?: Array<{
    industry: string;
    weight: number;
    [key: string]: unknown;
  }>;
  manager_profile?: ManagerProfile;
  [key: string]: unknown;
}

/** 经理画像 */
export interface ManagerProfile {
  name?: string;
  tenure_years?: number;
  history?: Array<{
    period: string;
    fund?: string;
    scale?: number;
    return?: number;
    [key: string]: unknown;
  }>;
  [key: string]: unknown;
}

/** 现金流（份额变动 + 机构持有） */
export interface Cashflow {
  fund_code: string;
  dates?: string[];
  share_change?: number[];
  institution_holding?: number[];
  [key: string]: unknown;
}

/** 业绩归因（3 列对比） */
export interface PerformanceAttribution {
  metrics: string[];
  fund: number[];
  peer_avg: number[];
  hs300?: number[];
  [key: string]: unknown;
}

/** LLM 报告 */
export interface LlmReport {
  fund_code: string;
  markdown?: string;
  json?: Record<string, unknown>;
  references?: Array<{
    label: string;
    anchor?: string;
    [key: string]: unknown;
  }>;
  [key: string]: unknown;
}

// ---------------------------------------------------------------------------
// 策略
// ---------------------------------------------------------------------------
export interface StrategySummary {
  strategy_id: string;
  prototype_id: string;
  domain: string;
  rank_in_domain?: number | null;
  composite_score?: number | null;
  annual_return?: number | null;
  sharpe?: number | null;
  max_drawdown?: number | null;
  adopted: boolean;
  disabled: boolean;
}

export interface StrategyDetail extends StrategySummary {
  prototype_name?: string;
  mind_model?: string;
  params?: Record<string, unknown>;
  param_diff?: string;
  backtest?: Record<string, unknown>;
  [key: string]: unknown;
}

/** 策略现金流 */
export interface StrategyCashflow {
  dates?: string[];
  share_change?: number[];
  institution_holding?: number[];
  [key: string]: unknown;
}

// ---------------------------------------------------------------------------
// 发现
// ---------------------------------------------------------------------------
export interface DiscoverResult {
  /** 领域名 -> 基金代码列表（Top-5） */
  domains: Record<string, string[]>;
  window: string;
}

export interface DiscoverReasons {
  fund_code: string;
  reasons: string[];
}

// ---------------------------------------------------------------------------
// 观察池 / 信号
// ---------------------------------------------------------------------------
export interface ObservationPool {
  pool: string[];
}

export interface ObservationOpResult {
  code: string;
  in_pool: boolean;
}

/** 信号档位（与后端 src/signal/models.py SignalLevel 对齐，中文） */
export type SignalLevel = "加仓" | "持有" | "减仓" | "止损";

/**
 * 信号（与后端 src/signal/models.py Signal 对齐）。
 *
 * 后端字段：
 * - level: 四档之一（加仓/持有/减仓/止损）
 * - reasons: 触发理由列表（数组，每条含【依据：指标=值】）
 * - score: 加权综合得分
 */
export interface Signal {
  fund_code: string;
  date?: string;
  level: SignalLevel;
  reasons: string[];
  score: number;
  signals_detail?: Array<Record<string, unknown>>;
  [key: string]: unknown;
}

// ---------------------------------------------------------------------------
// 配置 / 影响
// ---------------------------------------------------------------------------
export interface AppConfig {
  observation_pool?: string[];
  signal_rules?: unknown[];
  [key: string]: unknown;
}

export interface ChangeImpact {
  field: string;
  affected_funds: string[];
  description?: string;
  [key: string]: unknown;
}

export interface ConfigUpdateResult {
  impacts: ChangeImpact[];
  affected_count: number;
}

export interface ConfigHistoryEntry {
  commit: string;
  date: string;
  message: string;
  author?: string;
}

export interface ConfigHistory {
  history: ConfigHistoryEntry[];
}

// ---------------------------------------------------------------------------
// 系统
// ---------------------------------------------------------------------------
export interface SystemStatus {
  data_freshness: {
    total?: number;
    stale?: number;
    [key: string]: unknown;
  };
  last_run?: string | null;
  active_jobs: number;
  observation_pool_size: number;
  strategy_count: number;
}

export interface HealthStatus {
  status: string;
  version: string;
}
