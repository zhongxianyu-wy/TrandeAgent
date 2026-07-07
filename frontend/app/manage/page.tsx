/**
 * T17: 管理台首页 `/manage`。
 * 导航入口：配置编辑 / 观察池管理 / 任务监控。
 * + 系统状态概览 + 已采用策略 + 手动触发。
 */
"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Settings,
  Eye,
  ListChecks,
  Database,
  FlaskConical,
  Sparkles,
  RotateCcw,
} from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPost } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type {
  Job,
  PaginatedData,
  StrategySummary,
  SystemStatus,
} from "@/types/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { JobStatusBadge } from "@/components/common/JobStatusBadge";
import { CardSkeleton } from "@/components/common/LoadingSkeleton";

const ENTRIES = [
  {
    href: "/manage/config",
    title: "规则配置",
    desc: "YAML 表单化编辑 + 影响范围 + 版本回滚",
    icon: Settings,
  },
  {
    href: "/manage/observation",
    title: "观察池管理",
    desc: "观察池增删 + 信号查看",
    icon: Eye,
  },
  {
    href: "/manage/jobs",
    title: "任务监控",
    desc: "数据刷新 / 回测 / 分析任务",
    icon: ListChecks,
  },
] as const;

export default function ManagePage() {
  const qc = useQueryClient();
  const statusQ = useQuery({
    queryKey: queryKeys.system.status(),
    queryFn: () => apiGet<SystemStatus>("/api/system/status"),
  });
  const adoptedQ = useQuery({
    queryKey: queryKeys.strategies.list({ sort: "score", size: 50 }),
    queryFn: () =>
      apiGet<PaginatedData<StrategySummary>>("/api/strategies", {
        sort: "score",
        size: 50,
      }),
  });
  const jobsQ = useQuery({
    queryKey: queryKeys.jobs.list({ limit: 5 }),
    queryFn: () => apiGet<{ items: Job[] }>("/api/jobs", { limit: 5 }),
  });

  // 通用任务触发
  const triggerM = useMutation({
    mutationFn: (type: "refresh-data" | "backtest") => {
      if (type === "refresh-data") {
        return apiPost<{ job_id: string }>("/api/jobs/refresh-data", {});
      }
      return apiPost<{ job_id: string }>("/api/jobs/backtest", { count: 50 });
    },
    onSuccess: (d, type) => {
      toast.success(
        `${type === "refresh-data" ? "数据刷新" : "回测"}已触发（${d.job_id.slice(0, 8)}）`,
      );
      qc.invalidateQueries({ queryKey: queryKeys.jobs.all });
    },
    onError: (e: unknown) =>
      toast.error(`触发失败：${e instanceof Error ? e.message : "未知"}`),
  });

  const adopted = (adoptedQ.data?.items ?? []).filter((s) => s.adopted);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">管理台</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          配置 · 观察池 · 策略 · 任务
        </p>
      </div>

      {/* 导航卡片 */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {ENTRIES.map((e) => {
          const Icon = e.icon;
          return (
            <Link key={e.href} href={e.href}>
              <Card className="h-full transition-shadow hover:shadow-md">
                <CardContent className="flex h-full items-start gap-3 p-5">
                  <div className="flex h-10 w-10 items-center justify-center rounded-md bg-primary/10 text-primary">
                    <Icon className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="font-medium">{e.title}</div>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {e.desc}
                    </p>
                  </div>
                </CardContent>
              </Card>
            </Link>
          );
        })}
      </div>

      {/* 系统状态 + 手动触发 */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>系统状态</CardTitle>
            <CardDescription>数据新鲜度与活跃任务</CardDescription>
          </CardHeader>
          <CardContent>
            {statusQ.isLoading ? (
              <CardSkeleton />
            ) : (
              <div className="grid grid-cols-2 gap-4 text-sm">
                <Stat
                  label="数据总数"
                  value={`${statusQ.data?.data_freshness?.total ?? 0} 只`}
                />
                <Stat
                  label="待更新"
                  value={`${statusQ.data?.data_freshness?.stale ?? 0} 只`}
                  tone={statusQ.data?.data_freshness?.stale ? "warn" : undefined}
                />
                <Stat
                  label="活跃任务"
                  value={`${statusQ.data?.active_jobs ?? 0}`}
                />
                <Stat
                  label="上次运行"
                  value={statusQ.data?.last_run ?? "—"}
                />
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>手动触发</CardTitle>
            <CardDescription>立即运行数据/回测任务</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <Button
              variant="outline"
              className="w-full justify-start"
              onClick={() => triggerM.mutate("refresh-data")}
              disabled={triggerM.isPending}
            >
              <Database className="mr-2 h-4 w-4" /> 触发数据刷新
            </Button>
            <Button
              variant="outline"
              className="w-full justify-start"
              onClick={() => triggerM.mutate("backtest")}
              disabled={triggerM.isPending}
            >
              <FlaskConical className="mr-2 h-4 w-4" /> 触发策略回测
            </Button>
            <Link href="/manage/jobs" className="block">
              <Button variant="ghost" className="w-full justify-start">
                <ListChecks className="mr-2 h-4 w-4" /> 查看任务进度
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>

      {/* 已采用策略 + 最近任务 */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="h-4 w-4" /> 已采用策略
            </CardTitle>
            <CardDescription>策略管理（停用请进详情页）</CardDescription>
          </CardHeader>
          <CardContent>
            {adopted.length === 0 ? (
              <div className="py-4 text-center text-sm text-muted-foreground">
                暂无已采用策略
              </div>
            ) : (
              <ul className="space-y-2 text-sm">
                {adopted.slice(0, 8).map((s) => (
                  <li
                    key={s.strategy_id}
                    className="flex items-center justify-between"
                  >
                    <Link
                      href={`/strategies/${s.strategy_id}`}
                      className="font-medium text-primary hover:underline"
                    >
                      {s.strategy_id}
                    </Link>
                    <Badge variant="outline">{s.domain}</Badge>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <RotateCcw className="h-4 w-4" /> 最近任务
            </CardTitle>
            <CardDescription>最新 5 个任务</CardDescription>
          </CardHeader>
          <CardContent>
            {(jobsQ.data?.items?.length ?? 0) === 0 ? (
              <div className="py-4 text-center text-sm text-muted-foreground">
                暂无任务
              </div>
            ) : (
              <ul className="space-y-2 text-sm">
                {jobsQ.data?.items.slice(0, 5).map((j) => (
                  <li
                    key={j.job_id}
                    className="flex items-center justify-between"
                  >
                    <span className="truncate font-mono text-xs text-muted-foreground">
                      {j.type} · {j.job_id.slice(0, 8)}
                    </span>
                    <JobStatusBadge status={j.status} />
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "warn";
}) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div
        className={`mt-0.5 font-medium tabular-nums ${
          tone === "warn" ? "text-warn" : ""
        }`}
      >
        {value}
      </div>
    </div>
  );
}
