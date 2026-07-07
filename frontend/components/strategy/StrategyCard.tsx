/**
 * T06: 策略卡片（用于策略池 Top-5 展示）。
 */
"use client";

import Link from "next/link";
import { Star, ShieldCheck } from "lucide-react";
import type { StrategySummary } from "@/types/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  cn,
  formatNumber,
  formatPercent,
  returnColorClass,
} from "@/lib/utils";

export function StrategyCard({ s }: { s: StrategySummary }) {
  return (
    <Link href={`/strategies/${s.strategy_id}`} className="block">
      <Card className="transition-shadow hover:shadow-md">
        <div className="flex items-start justify-between p-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="truncate text-sm font-semibold">
                {s.strategy_id}
              </span>
              {s.adopted ? (
                <Badge variant="success" className="gap-1">
                  <ShieldCheck className="h-3 w-3" /> 已采用
                </Badge>
              ) : null}
              {s.disabled ? <Badge variant="danger">已停用</Badge> : null}
            </div>
            <div className="mt-1 truncate text-xs text-muted-foreground">
              {s.prototype_id} · {s.domain}
            </div>
          </div>
          {s.rank_in_domain != null ? (
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              <Star className="h-3 w-3" /> #{s.rank_in_domain}
            </div>
          ) : null}
        </div>
        <div className="grid grid-cols-3 gap-2 px-4 pb-4 text-sm">
          <Metric
            label="综合"
            value={formatNumber(s.composite_score ?? null, 2)}
          />
          <Metric
            label="年化"
            value={formatPercent(s.annual_return ?? null)}
            className={returnColorClass(s.annual_return ?? null)}
          />
          <Metric
            label="夏普"
            value={formatNumber(s.sharpe ?? null, 2)}
          />
        </div>
      </Card>
    </Link>
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
      <div className={cn("text-sm font-medium tabular-nums", className)}>
        {value}
      </div>
    </div>
  );
}
