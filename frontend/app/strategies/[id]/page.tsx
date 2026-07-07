/**
 * T10: 策略详情页 `/strategies/[id]`。
 * - 策略基本信息卡
 * - 多周期柱状图（T07）
 * - 净值+回撤+基准主图（T08）
 * - 现金流时序图（T09）
 * - 操作：采用 / 停用
 */
"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { ShieldCheck, Power, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPost } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type {
  Period,
  PeriodReturn,
  NavCurve,
  StrategyCashflow,
  StrategyDetail,
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { PeriodReturnChart } from "@/components/charts/PeriodReturnChart";
import { NavCurveChart } from "@/components/charts/NavCurveChart";
import { CashflowChart } from "@/components/charts/CashflowChart";
import { ChartSkeleton } from "@/components/common/LoadingSkeleton";
import {
  formatNumber,
  formatPercent,
  returnColorClass,
} from "@/lib/utils";

const PERIODS: { value: Period; label: string }[] = [
  { value: "daily", label: "日度" },
  { value: "weekly", label: "周度" },
  { value: "monthly", label: "月度" },
  { value: "quarterly", label: "季度" },
  { value: "yearly", label: "年度" },
];

export default function StrategyDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const qc = useQueryClient();
  const [period, setPeriod] = useState<Period>("monthly");

  const detailQ = useQuery({
    queryKey: queryKeys.strategies.detail(id),
    queryFn: () => apiGet<StrategyDetail>(`/api/strategies/${id}`),
  });

  const tsQ = useQuery({
    queryKey: queryKeys.strategies.timeseries(id, period),
    queryFn: () =>
      apiGet<PeriodReturn>(`/api/strategies/${id}/timeseries`, { period }),
  });

  const navQ = useQuery({
    queryKey: queryKeys.strategies.nav(id, {}),
    queryFn: () => apiGet<NavCurve>(`/api/strategies/${id}/nav`),
  });

  const cashflowQ = useQuery({
    queryKey: queryKeys.strategies.cashflow(id),
    queryFn: () => apiGet<StrategyCashflow>(`/api/strategies/${id}/cashflow`),
  });

  const adoptM = useMutation({
    mutationFn: () => apiPost(`/api/strategies/${id}/adopt`),
    onSuccess: () => {
      toast.success("已采用策略");
      qc.invalidateQueries({ queryKey: queryKeys.strategies.detail(id) });
      qc.invalidateQueries({ queryKey: queryKeys.strategies.all });
    },
    onError: (e: unknown) =>
      toast.error(`采用失败：${e instanceof Error ? e.message : "未知"}`),
  });

  const disableM = useMutation({
    mutationFn: () => apiPost(`/api/strategies/${id}/disable`),
    onSuccess: () => {
      toast.success("已停用策略");
      qc.invalidateQueries({ queryKey: queryKeys.strategies.detail(id) });
      qc.invalidateQueries({ queryKey: queryKeys.strategies.all });
    },
    onError: (e: unknown) =>
      toast.error(`停用失败：${e instanceof Error ? e.message : "未知"}`),
  });

  const s = detailQ.data;

  return (
    <div className="space-y-6">
      {/* 基本信息卡 */}
      <Card>
        <CardContent className="p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-semibold tracking-tight">
                  {id}
                </h1>
                {s?.adopted ? (
                  <Badge variant="success" className="gap-1">
                    <ShieldCheck className="h-3 w-3" /> 已采用
                  </Badge>
                ) : null}
                {s?.disabled ? (
                  <Badge variant="danger">已停用</Badge>
                ) : null}
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                {s?.prototype_name || s?.prototype_id} · 领域{" "}
                {s?.domain ?? "—"}
              </p>
              {s?.mind_model ? (
                <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
                  心智模型：{String(s.mind_model)}
                </p>
              ) : null}
              {s?.param_diff ? (
                <p className="mt-1 text-xs text-muted-foreground">
                  参数差异：{String(s.param_diff)}
                </p>
              ) : null}
            </div>
            <div className="flex flex-col items-end gap-3">
              <div className="grid grid-cols-3 gap-4 text-right text-sm">
                <Metric
                  label="年化"
                  value={formatPercent(s?.annual_return ?? null)}
                  className={returnColorClass(s?.annual_return ?? null)}
                />
                <Metric
                  label="夏普"
                  value={formatNumber(s?.sharpe ?? null, 2)}
                />
                <Metric
                  label="最大回撤"
                  value={formatPercent(s?.max_drawdown ?? null)}
                  className="text-down"
                />
              </div>
              <div className="flex gap-2">
                {s?.adopted ? (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => disableM.mutate()}
                    disabled={disableM.isPending}
                  >
                    <Power className="mr-1 h-3.5 w-3.5" /> 停用
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    onClick={() => adoptM.mutate()}
                    disabled={adoptM.isPending || s?.disabled}
                  >
                    <ShieldCheck className="mr-1 h-3.5 w-3.5" /> 采用策略
                  </Button>
                )}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 多周期柱状图 */}
      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <div>
            <CardTitle>多周期收益对比</CardTitle>
            <CardDescription>本策略 vs 基准</CardDescription>
          </div>
          <Select value={period} onValueChange={(v) => setPeriod(v as Period)}>
            <SelectTrigger className="w-28">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PERIODS.map((p) => (
                <SelectItem key={p.value} value={p.value}>
                  {p.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CardHeader>
        <CardContent>
          {tsQ.isLoading ? (
            <ChartSkeleton />
          ) : (
            <PeriodReturnChart data={tsQ.data} />
          )}
        </CardContent>
      </Card>

      {/* 净值曲线主图 */}
      <Card>
        <CardHeader>
          <CardTitle>净值曲线 / 回撤 / 基准</CardTitle>
          <CardDescription>支持滚轮缩放（大数据自动采样）</CardDescription>
        </CardHeader>
        <CardContent>
          {navQ.isLoading ? <ChartSkeleton /> : <NavCurveChart data={navQ.data} />}
        </CardContent>
      </Card>

      {/* 现金流时序 */}
      <Card>
        <CardHeader>
          <CardTitle>现金流时序</CardTitle>
          <CardDescription>份额变动 + 机构持有变化</CardDescription>
        </CardHeader>
        <CardContent>
          {cashflowQ.isLoading ? (
            <ChartSkeleton />
          ) : (
            <CashflowChart data={cashflowQ.data} />
          )}
        </CardContent>
      </Card>

      {/* 查看持仓/重新生成入口 */}
      <div className="flex justify-end">
        <Button
          variant="ghost"
          size="sm"
          onClick={() =>
            toast.info("请在管理台触发策略重新生成任务")
          }
        >
          <RefreshCw className="mr-1 h-3.5 w-3.5" /> 重新生成策略
        </Button>
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  className,
}: {
  label: string;
  value: string;
  className?: string;
}) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={`font-medium tabular-nums ${className ?? ""}`}>
        {value}
      </div>
    </div>
  );
}
