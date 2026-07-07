/**
 * T17: 任务监控 `/manage/jobs`。
 * - 列表（含状态/进度/类型）
 * - 手动触发（refresh-data / backtest）
 * - 进度条
 */
"use client";

import { useState } from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { Database, FlaskConical, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPost } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type { Job, JobStatus } from "@/types/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { JobStatusBadge } from "@/components/common/JobStatusBadge";
import { TableSkeleton } from "@/components/common/LoadingSkeleton";
import { cn } from "@/lib/utils";

const STATUS_FILTERS: (JobStatus | "all")[] = [
  "all",
  "running",
  "pending",
  "succeeded",
  "failed",
];

export default function JobsPage() {
  const qc = useQueryClient();
  const [status, setStatus] = useState<JobStatus | "all">("all");

  const jobsQ = useQuery({
    queryKey: queryKeys.jobs.list({ status, limit: 100 }),
    queryFn: () =>
      apiGet<{ items: Job[] }>("/api/jobs", {
        status: status === "all" ? undefined : status,
        limit: 100,
      }),
    refetchInterval: 5000,
  });

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

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">任务监控</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            数据刷新 / 回测 / 分析，每 5 秒自动刷新
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => triggerM.mutate("refresh-data")}
            disabled={triggerM.isPending}
          >
            <Database className="mr-1 h-3.5 w-3.5" /> 数据刷新
          </Button>
          <Button
            size="sm"
            onClick={() => triggerM.mutate("backtest")}
            disabled={triggerM.isPending}
          >
            <FlaskConical className="mr-1 h-3.5 w-3.5" /> 回测
          </Button>
        </div>
      </div>

      {/* 状态筛选 */}
      <div className="flex flex-wrap gap-2">
        {STATUS_FILTERS.map((s) => (
          <Button
            key={s}
            variant={status === s ? "default" : "outline"}
            size="sm"
            onClick={() => setStatus(s)}
          >
            {s === "all"
              ? "全部"
              : s === "running"
                ? "运行中"
                : s === "pending"
                  ? "等待"
                  : s === "succeeded"
                    ? "成功"
                    : "失败"}
          </Button>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>任务列表</CardTitle>
          <CardDescription>共 {jobsQ.data?.items?.length ?? 0} 个</CardDescription>
        </CardHeader>
        <CardContent>
          {jobsQ.isLoading ? (
            <TableSkeleton rows={8} cols={5} />
          ) : (jobsQ.data?.items?.length ?? 0) === 0 ? (
            <div className="py-8 text-center text-sm text-muted-foreground">
              暂无任务
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>类型</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead className="w-1/3">进度</TableHead>
                  <TableHead>开始时间</TableHead>
                  <TableHead>结束时间</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {jobsQ.data?.items.map((j) => (
                  <TableRow key={j.job_id}>
                    <TableCell>
                      <div className="font-medium">{j.type}</div>
                      <div className="font-mono text-xs text-muted-foreground">
                        {j.job_id.slice(0, 8)}
                      </div>
                    </TableCell>
                    <TableCell>
                      <span className="flex items-center gap-1">
                        {j.status === "running" ? (
                          <Loader2 className="h-3 w-3 animate-spin text-warn" />
                        ) : null}
                        <JobStatusBadge status={j.status} />
                      </span>
                    </TableCell>
                    <TableCell>
                      <ProgressBar value={j.progress} status={j.status} />
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {fmt(j.started_at)}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {fmt(j.finished_at)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function ProgressBar({
  value,
  status,
}: {
  value: number;
  status: string;
}) {
  const pct = Math.min(100, Math.max(0, (value ?? 0) * 100));
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
        <div
          className={cn(
            "h-full rounded-full transition-all",
            status === "failed"
              ? "bg-down"
              : status === "succeeded"
                ? "bg-up"
                : "bg-primary",
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-10 text-right text-xs tabular-nums text-muted-foreground">
        {pct.toFixed(0)}%
      </span>
    </div>
  );
}

function fmt(s?: string | null): string {
  if (!s) return "—";
  try {
    return new Date(s).toLocaleString("zh-CN", { hour12: false });
  } catch {
    return s;
  }
}
