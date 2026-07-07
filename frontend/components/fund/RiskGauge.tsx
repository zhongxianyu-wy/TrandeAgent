/**
 * T12: 风险指标仪表盘（夏普/回撤/波动率）。
 * 单仪表盘 + 关键指标卡片。
 */
"use client";

import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import { Gauge } from "lucide-react";
import type { FundIndicators } from "@/types/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { formatNumber, formatPercent } from "@/lib/utils";

export interface RiskGaugeProps {
  indicators: FundIndicators | null | undefined;
}

export function RiskGaugeCard({ indicators }: RiskGaugeProps) {
  const sharpe = indicators?.l2_performance?.sharpe ?? null;
  const dd = indicators?.l2_performance?.max_drawdown ?? null;
  const vol = indicators?.l2_performance?.volatility ?? null;

  // 综合评分：夏普为主指标，越高越好
  const score = sharpe ?? 0;
  const option = useMemo(() => {
    return {
      series: [
        {
          type: "gauge" as const,
          min: -2,
          max: 4,
          axisLine: {
            lineStyle: {
              width: 12,
              color: [
                [0.3, "#EF4444"],
                [0.6, "#F59E0B"],
                [1, "#10B981"],
              ],
            },
          },
          pointer: { width: 5, length: "60%" },
          axisTick: { show: false },
          splitLine: { length: 12, lineStyle: { color: "#fff" } },
          axisLabel: { color: "#94a3b8", fontSize: 10, distance: -28 },
          detail: {
            formatter: (v: number) => v.toFixed(2),
            color: "#0f172a",
            fontSize: 22,
            offsetCenter: [0, "70%"],
          },
          data: [{ value: score, name: "夏普" }],
        },
      ],
    };
  }, [score]);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Gauge className="h-4 w-4" /> 风险仪表盘
        </CardTitle>
        <CardDescription>夏普 / 最大回撤 / 波动率</CardDescription>
      </CardHeader>
      <CardContent>
        <ReactECharts
          option={option}
          style={{ height: 220, width: "100%" }}
          opts={{ renderer: "canvas" }}
          notMerge
          lazyUpdate
        />
        <div className="mt-2 grid grid-cols-3 gap-3 text-center text-sm">
          <RiskMetric label="夏普" value={formatNumber(sharpe, 2)} />
          <RiskMetric
            label="最大回撤"
            value={formatPercent(dd)}
            tone="down"
          />
          <RiskMetric label="波动率" value={formatPercent(vol)} />
        </div>
      </CardContent>
    </Card>
  );
}

function RiskMetric({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "down" | "up";
}) {
  return (
    <div className="rounded-md border p-2">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div
        className={`mt-1 font-medium tabular-nums ${
          tone === "down" ? "text-down" : ""
        }`}
      >
        {value}
      </div>
    </div>
  );
}
