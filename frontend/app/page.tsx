/**
 * T05: 首页 Dashboard（今日总览）。
 * - 今日组合表现卡片（观察池平均收益/异动 Top-3）
 * - 今日信号列表（加仓/减仓/止损分组）
 * - 今日候选 Top-5
 * - 数据新鲜度（顶栏已有，这里再汇总）
 */
"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import {
  ArrowUpRight,
  ArrowDownRight,
  TrendingUp,
  Trophy,
  Activity,
  AlertCircle,
  Minus,
} from "lucide-react";
import { apiGet } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type {
  ObservationPool,
  Signal,
  SystemStatus,
  DiscoverResult,
  StrategySummary,
  PaginatedData,
} from "@/types/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  CardSkeleton,
  ListSkeleton,
  TableSkeleton,
} from "@/components/common/LoadingSkeleton";
import {
  formatNumber,
  formatPercent,
  returnColorClass,
  signalColorClass,
} from "@/lib/utils";

const TODAY = "today";

export default function DashboardPage() {
  const statusQ = useQuery({
    queryKey: queryKeys.system.status(),
    queryFn: () => apiGet<SystemStatus>("/api/system/status"),
  });
  const poolQ = useQuery({
    queryKey: queryKeys.observation.all,
    queryFn: () => apiGet<ObservationPool>("/api/observation"),
  });
  const discoverQ = useQuery({
    queryKey: queryKeys.discover.all(TODAY),
    queryFn: () => apiGet<DiscoverResult>(`/api/discover`, { window: TODAY }),
  });
  const topStrategyQ = useQuery({
    queryKey: queryKeys.strategies.list({ sort: "score", size: 5 }),
    queryFn: () =>
      apiGet<PaginatedData<StrategySummary>>("/api/strategies", {
        sort: "score",
        size: 5,
      }),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">今日总览</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            观察池 · 信号 · 推荐 状态一览
          </p>
        </div>
      </div>

      {/* KPI 卡片 */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {statusQ.isLoading ? (
          <>
            <CardSkeleton />
            <CardSkeleton />
            <CardSkeleton />
            <CardSkeleton />
          </>
        ) : (
          <>
            <KpiCard
              icon={<TrendingUp className="h-4 w-4" />}
              label="观察池规模"
              value={`${statusQ.data?.observation_pool_size ?? 0} 只`}
              hint={`当前活跃任务 ${statusQ.data?.active_jobs ?? 0}`}
            />
            <KpiCard
              icon={<Activity className="h-4 w-4" />}
              label="策略总数"
              value={`${statusQ.data?.strategy_count ?? 0} 个`}
              hint={`上次运行 ${statusQ.data?.last_run ?? "—"}`}
            />
            <KpiCard
              icon={<ArrowUpRight className="h-4 w-4 text-up" />}
              label="数据总数"
              value={`${(statusQ.data?.data_freshness?.total ?? 0)} 只`}
              hint={
                (statusQ.data?.data_freshness?.stale ?? 0) > 0
                  ? `${statusQ.data?.data_freshness?.stale} 只待更新`
                  : "数据已是最新"
              }
              hintTone={
                (statusQ.data?.data_freshness?.stale ?? 0) > 0
                  ? "warn"
                  : "up"
              }
            />
            <KpiCard
              icon={<Trophy className="h-4 w-4" />}
              label="今日候选"
              value={`${
                Object.values(discoverQ.data?.domains ?? {}).reduce(
                  (a, b) => a + (b?.length ?? 0),
                  0,
                )
              } 只`}
              hint="8 领域 Top-5"
            />
          </>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* 观察池 + 信号 */}
        <Card className="lg:col-span-2">
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <CardTitle>观察池</CardTitle>
              <CardDescription>当前关注的基金</CardDescription>
            </div>
            <Link
              href="/manage/observation"
              className="text-xs text-primary hover:underline"
            >
              管理 →
            </Link>
          </CardHeader>
          <CardContent>
            {poolQ.isLoading ? (
              <ListSkeleton items={4} />
            ) : (poolQ.data?.pool?.length ?? 0) === 0 ? (
              <div className="py-8 text-center text-sm text-muted-foreground">
                观察池为空，去
                <Link
                  href="/discover"
                  className="ml-1 text-primary hover:underline"
                >
                  发现
                </Link>{" "}
                添加基金
              </div>
            ) : (
              <div className="flex flex-wrap gap-2">
                {poolQ.data?.pool.map((code) => (
                  <Link key={code} href={`/funds/${code}`}>
                    <Badge variant="secondary" className="cursor-pointer">
                      {code}
                    </Badge>
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* 今日信号（聚合，简化展示观察池中首只基金的信号作为样例） */}
        <SignalCard pool={poolQ.data?.pool ?? []} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* 今日候选 Top-5 */}
        <Card>
          <CardHeader>
            <CardTitle>今日候选 Top-5</CardTitle>
            <CardDescription>发现页 8 领域推荐</CardDescription>
          </CardHeader>
          <CardContent>
            {discoverQ.isLoading ? (
              <ListSkeleton items={5} />
            ) : (
              <CandidateList domains={discoverQ.data?.domains ?? {}} />
            )}
          </CardContent>
        </Card>

        {/* 竞技场亮点 Top-1 */}
        <Card>
          <CardHeader>
            <CardTitle>竞技场亮点 Top-1</CardTitle>
            <CardDescription>综合得分最高的策略</CardDescription>
          </CardHeader>
          <CardContent>
            {topStrategyQ.isLoading ? (
              <TableSkeleton rows={1} cols={3} />
            ) : topStrategyQ.data?.items?.[0] ? (
              <TopStrategy s={topStrategyQ.data.items[0]} />
            ) : (
              <div className="py-8 text-center text-sm text-muted-foreground">
                暂无策略
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function KpiCard({
  icon,
  label,
  value,
  hint,
  hintTone,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  hint?: string;
  hintTone?: "up" | "down" | "warn";
}) {
  return (
    <Card>
      <CardContent className="p-5">
        <div className="flex items-center justify-between">
          <div className="text-sm text-muted-foreground">{label}</div>
          <div className="text-muted-foreground">{icon}</div>
        </div>
        <div className="mt-2 text-2xl font-semibold tabular-nums">{value}</div>
        {hint ? (
          <div
            className={`mt-1 text-xs ${
              hintTone === "warn"
                ? "text-warn"
                : hintTone === "up"
                  ? "text-up"
                  : hintTone === "down"
                    ? "text-down"
                    : "text-muted-foreground"
            }`}
          >
            {hint}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function CandidateList({
  domains,
}: {
  domains: Record<string, string[]>;
}) {
  const all: { domain: string; code: string }[] = [];
  Object.entries(domains).forEach(([d, codes]) => {
    codes?.slice(0, 5).forEach((c) => all.push({ domain: d, code: c }));
  });
  if (all.length === 0)
    return (
      <div className="py-6 text-center text-sm text-muted-foreground">
        暂无推荐
      </div>
    );
  return (
    <ul className="space-y-2 text-sm">
      {all.slice(0, 5).map((c, i) => (
        <li key={`${c.domain}-${c.code}`} className="flex items-center gap-2">
          <span className="w-5 text-xs text-muted-foreground">{i + 1}</span>
          <Link
            href={`/funds/${c.code}`}
            className="font-medium text-primary hover:underline"
          >
            {c.code}
          </Link>
          <Badge variant="outline" className="text-xs">
            {c.domain}
          </Badge>
        </li>
      ))}
    </ul>
  );
}

function TopStrategy({ s }: { s: StrategySummary }) {
  return (
    <Link href={`/strategies/${s.strategy_id}`} className="block">
      <div className="flex items-center justify-between">
        <div>
          <div className="font-semibold">{s.strategy_id}</div>
          <div className="text-xs text-muted-foreground">
            {s.prototype_id} · {s.domain}
          </div>
        </div>
        <Trophy className="h-6 w-6 text-warn" />
      </div>
      <div className="mt-3 grid grid-cols-3 gap-3 text-sm">
        <div>
          <div className="text-xs text-muted-foreground">综合</div>
          <div className="font-medium tabular-nums">
            {formatNumber(s.composite_score ?? null, 2)}
          </div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">年化</div>
          <div
            className={`font-medium tabular-nums ${returnColorClass(
              s.annual_return ?? null,
            )}`}
          >
            {formatPercent(s.annual_return ?? null)}
          </div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">夏普</div>
          <div className="font-medium tabular-nums">
            {formatNumber(s.sharpe ?? null, 2)}
          </div>
        </div>
      </div>
    </Link>
  );
}

/** 信号卡片：取观察池首只基金的信号作为今日信号样例 */
function SignalCard({ pool }: { pool: string[] }) {
  const first = pool[0];
  const signalsQ = useQuery({
    queryKey: first ? queryKeys.observation.signals(first) : ["observation", "signals", "noop"],
    queryFn: () =>
      first
        ? apiGet<Signal[]>(`/api/observation/${first}/signals`)
        : Promise.resolve([] as Signal[]),
    enabled: !!first,
  });

  const grouped = (signalsQ.data ?? []).reduce<
    Record<string, Signal[]>
  >((acc, sig) => {
    // 后端 level 为中文（加仓/持有/减仓/止损）
    const key = (sig.level || "其他") as string;
    (acc[key] ??= []).push(sig);
    return acc;
  }, {});

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <AlertCircle className="h-4 w-4" /> 今日信号
        </CardTitle>
        <CardDescription>
          {first ? `样本：${first}` : "观察池为空"}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {!first ? (
          <div className="py-6 text-center text-sm text-muted-foreground">
            加入基金后显示信号
          </div>
        ) : signalsQ.isLoading ? (
          <ListSkeleton items={3} />
        ) : (signalsQ.data?.length ?? 0) === 0 ? (
          <div className="py-6 text-center text-sm text-muted-foreground">
            暂无信号
          </div>
        ) : (
          <div className="space-y-2">
            {(["加仓", "持有", "减仓", "止损"] as const).map((lv) => {
              const list = grouped[lv] ?? [];
              if (list.length === 0) return null;
              const Icon =
                lv === "加仓"
                  ? ArrowUpRight
                  : lv === "减仓"
                    ? ArrowDownRight
                    : lv === "止损"
                      ? AlertCircle
                      : Minus;
              return list.slice(0, 3).map((sig, i) => (
                <div
                  key={`${lv}-${i}`}
                  className="flex items-center justify-between rounded-md border p-2"
                >
                  <div className="flex items-center gap-2 text-sm">
                    <Icon
                      className={`h-4 w-4 ${signalColorClass(lv)}`}
                    />
                    <span className="font-medium">{lv}</span>
                    <span className="text-muted-foreground">
                      {sig.fund_code}
                    </span>
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {sig.date ?? "—"}
                  </span>
                </div>
              ));
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
