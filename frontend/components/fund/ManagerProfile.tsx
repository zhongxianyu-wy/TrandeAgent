/**
 * T11: 经理画像时间轴（任期/历史业绩/管理规模变化）。
 */
"use client";

import { Briefcase } from "lucide-react";
import type { ManagerProfile, Holdings } from "@/types/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatNumber, formatPercent } from "@/lib/utils";

export interface ManagerProfileProps {
  holdings: Holdings | null | undefined;
}

export function ManagerProfileCard({ holdings }: ManagerProfileProps) {
  const m: ManagerProfile | undefined = holdings?.manager_profile;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Briefcase className="h-4 w-4" /> 经理画像
        </CardTitle>
        <CardDescription>
          {m?.name ?? "—"}
          {m?.tenure_years != null
            ? ` · 任职 ${formatNumber(m.tenure_years, 1)} 年`
            : ""}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {!m?.history || m.history.length === 0 ? (
          <div className="py-6 text-center text-sm text-muted-foreground">
            暂无经理历史数据
          </div>
        ) : (
          <ol className="relative space-y-4 border-l pl-5">
            {m.history.map((h, i) => (
              <li key={i} className="relative">
                <span className="absolute -left-[26px] top-1 h-3 w-3 rounded-full border-2 border-primary bg-background" />
                <div className="flex items-center justify-between">
                  <div className="text-sm font-medium">
                    {h.fund ?? "—"}
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {h.period ?? ""}
                  </span>
                </div>
                <div className="mt-1 flex flex-wrap gap-2 text-xs">
                  {h.scale != null ? (
                    <Badge variant="secondary">规模 {formatNumber(h.scale, 0)}</Badge>
                  ) : null}
                  {h.return != null ? (
                    <Badge variant="outline">收益 {formatPercent(h.return)}</Badge>
                  ) : null}
                </div>
              </li>
            ))}
          </ol>
        )}
      </CardContent>
    </Card>
  );
}
