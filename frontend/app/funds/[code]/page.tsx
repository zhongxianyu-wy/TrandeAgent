/**
 * T14: 单基金深度解读页 `/funds/[code]`。
 * 组装 6 个可视化模块：
 * - 经理画像（T11）
 * - 持仓雷达（T11）
 * - 业绩归因（T12）
 * - 风险仪表盘（T12）
 * - 现金流瀑布（T13）
 * - LLM 报告（T13）
 * 操作：加入观察池 / 触发 AI 重新分析
 */
"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { Eye, Sparkles, Star } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPost } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type {
  Cashflow,
  FundDetail,
  FundIndicators,
  Holdings,
  LlmReport,
  ObservationPool,
  PerformanceAttribution,
} from "@/types/api";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ManagerProfileCard } from "@/components/fund/ManagerProfile";
import { HoldingsRadar } from "@/components/fund/HoldingsRadar";
import { PerformanceAttributionTable } from "@/components/fund/PerformanceAttribution";
import { RiskGaugeCard } from "@/components/fund/RiskGauge";
import { CashflowWaterfall } from "@/components/fund/CashflowWaterfall";
import { LlmReportCard } from "@/components/fund/LlmReport";
import {
  formatNumber,
  formatPercent,
  formatScale,
  returnColorClass,
} from "@/lib/utils";

export default function FundDetailPage() {
  const params = useParams<{ code: string }>();
  const code = params.code;
  const qc = useQueryClient();

  const detailQ = useQuery({
    queryKey: queryKeys.funds.detail(code),
    queryFn: () => apiGet<FundDetail>(`/api/funds/${code}`),
  });
  const holdingsQ = useQuery({
    queryKey: queryKeys.funds.holdings(code),
    queryFn: () => apiGet<Holdings>(`/api/funds/${code}/holdings`),
  });
  const cashflowQ = useQuery({
    queryKey: queryKeys.funds.cashflow(code),
    queryFn: () => apiGet<Cashflow>(`/api/funds/${code}/cashflow`),
  });
  const reportQ = useQuery({
    queryKey: queryKeys.funds.report(code),
    queryFn: () => apiGet<LlmReport>(`/api/funds/${code}/report`),
  });
  const poolQ = useQuery({
    queryKey: queryKeys.observation.all,
    queryFn: () => apiGet<ObservationPool>("/api/observation"),
  });
  const reasonsQ = useQuery({
    queryKey: queryKeys.discover.reasons(code),
    queryFn: () =>
      apiGet<{ fund_code: string; reasons: string[] }>(
        `/api/discover/reasons/${code}`,
      ),
  });

  const inPool = (poolQ.data?.pool ?? []).includes(code);

  const addObsM = useMutation({
    mutationFn: () => apiPost(`/api/observation/${code}`),
    onSuccess: () => {
      toast.success("已加入观察池");
      qc.invalidateQueries({ queryKey: queryKeys.observation.all });
    },
    onError: (e: unknown) =>
      toast.error(`加入失败：${e instanceof Error ? e.message : "未知"}`),
  });

  const analyzeM = useMutation({
    mutationFn: () =>
      apiPost<{ job_id: string }>(`/api/funds/${code}/analyze`),
    onSuccess: (d) => {
      toast.success(`已触发 AI 重新分析（任务 ${d.job_id.slice(0, 8)}）`);
      qc.invalidateQueries({ queryKey: queryKeys.funds.report(code) });
    },
    onError: (e: unknown) =>
      toast.error(`分析失败：${e instanceof Error ? e.message : "未知"}`),
  });

  const f = detailQ.data;
  const ind: FundIndicators | undefined = f?.indicators;
  const perf: PerformanceAttribution | undefined =
    (f as unknown as { performance?: PerformanceAttribution })?.performance ??
    (holdingsQ.data as unknown as { performance?: PerformanceAttribution })
      ?.performance;

  return (
    <div className="space-y-6">
      {/* 头部 */}
      <Card>
        <CardContent className="p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-semibold tracking-tight">
                  {f?.fund_name || code}
                </h1>
                <Badge variant="outline">{code}</Badge>
                {f?.fund_category ? (
                  <Badge variant="secondary">{f.fund_category}</Badge>
                ) : null}
                {ind?.rating ? (
                  <Badge variant="success" className="gap-1">
                    <Star className="h-3 w-3" /> {ind.rating} 星
                  </Badge>
                ) : null}
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                经理 {f?.manager_names || "—"} · 成立{" "}
                {f?.establish_date || "—"} · 规模{" "}
                {formatScale(f?.latest_scale ?? null)}
                {f?.management_fee
                  ? ` · 管理费 ${(f.management_fee * 100).toFixed(2)}%`
                  : ""}
              </p>
              {reasonsQ.data?.reasons?.length ? (
                <div className="mt-2 flex flex-wrap gap-2">
                  {reasonsQ.data.reasons.slice(0, 3).map((r, i) => (
                    <Badge key={i} variant="outline" className="text-xs">
                      {r}
                    </Badge>
                  ))}
                </div>
              ) : null}
            </div>
            <div className="flex flex-col items-end gap-3">
              <div className="grid grid-cols-3 gap-4 text-right text-sm">
                <Metric
                  label="近 1 年"
                  value={formatPercent(ind?.l2_performance?.return_1y ?? null)}
                  className={returnColorClass(
                    ind?.l2_performance?.return_1y ?? null,
                  )}
                />
                <Metric
                  label="夏普"
                  value={formatNumber(ind?.l2_performance?.sharpe ?? null, 2)}
                />
                <Metric
                  label="最大回撤"
                  value={formatPercent(ind?.l2_performance?.max_drawdown ?? null)}
                  className="text-down"
                />
              </div>
              <div className="flex gap-2">
                <Button
                  variant={inPool ? "secondary" : "outline"}
                  size="sm"
                  onClick={() => addObsM.mutate()}
                  disabled={inPool || addObsM.isPending}
                >
                  <Eye className="mr-1 h-3.5 w-3.5" />
                  {inPool ? "已在观察池" : "加入观察池"}
                </Button>
                <Button
                  size="sm"
                  onClick={() => analyzeM.mutate()}
                  disabled={analyzeM.isPending}
                >
                  <Sparkles className="mr-1 h-3.5 w-3.5" />
                  {analyzeM.isPending ? "分析中…" : "触发 AI 重新分析"}
                </Button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 6 个模块 */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ManagerProfileCard holdings={holdingsQ.data} />
        <HoldingsRadar holdings={holdingsQ.data} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <PerformanceAttributionTable data={perf} />
        <RiskGaugeCard indicators={ind} />
      </div>

      <CashflowWaterfall data={cashflowQ.data} />

      <LlmReportCard data={reportQ.data} loading={reportQ.isLoading} />
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
