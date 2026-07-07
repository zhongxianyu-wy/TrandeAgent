/**
 * T13: 现金流瀑布图（季度份额变动）。
 * 使用 ECharts 的 waterfall 实现（堆叠 + 透明占位）。
 */
"use client";

import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import { Waves } from "lucide-react";
import type { Cashflow } from "@/types/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export interface CashflowWaterfallProps {
  data: Cashflow | null | undefined;
  height?: number;
}

export function CashflowWaterfall({ data, height = 320 }: CashflowWaterfallProps) {
  const option = useMemo(() => {
    const dates = (data?.dates as string[]) ?? [];
    const changes = (data?.share_change as number[]) ?? [];

    // 瀑布图：用透明占位柱 + 实际变动柱（正绿负红）
    let cumulative = 0;
    const placeholder: (number | null)[] = [];
    const positive: (number | null)[] = [];
    const negative: (number | null)[] = [];
    changes.forEach((v) => {
      if (v >= 0) {
        placeholder.push(cumulative);
        positive.push(v);
        negative.push(null);
      } else {
        placeholder.push(cumulative + v);
        positive.push(null);
        negative.push(-v);
      }
      cumulative += v;
    });

    return {
      animation: false,
      grid: { left: 56, right: 16, top: 40, bottom: 56 },
      tooltip: {
        trigger: "axis" as const,
        axisPointer: { type: "shadow" as const },
      },
      legend: {
        data: ["份额净流入", "份额净流出"],
        top: 4,
        right: 8,
        textStyle: { color: "#64748b" },
      },
      xAxis: {
        type: "category" as const,
        data: dates,
        axisLabel: { color: "#64748b", fontSize: 11 },
        axisLine: { lineStyle: { color: "#e5e5e5" } },
      },
      yAxis: {
        type: "value" as const,
        axisLabel: {
          color: "#64748b",
          fontSize: 11,
          formatter: (v: number) =>
            Math.abs(v) >= 1e8 ? `${(v / 1e8).toFixed(1)}亿` : v.toFixed(0),
        },
        splitLine: { lineStyle: { color: "#f1f5f9" } },
      },
      series: [
        {
          name: "占位",
          type: "bar" as const,
          stack: "wf",
          itemStyle: { borderColor: "transparent", color: "transparent" },
          data: placeholder,
          tooltip: { show: false },
          silent: true,
        },
        {
          name: "份额净流入",
          type: "bar" as const,
          stack: "wf",
          data: positive,
          itemStyle: { color: "#10B981" },
          barMaxWidth: 32,
        },
        {
          name: "份额净流出",
          type: "bar" as const,
          stack: "wf",
          data: negative,
          itemStyle: { color: "#EF4444" },
          barMaxWidth: 32,
        },
      ],
    };
  }, [data]);

  const hasData =
    ((data?.dates as string[] | undefined)?.length ?? 0) > 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Waves className="h-4 w-4" /> 现金流瀑布
        </CardTitle>
        <CardDescription>季度份额变动（绿正红负）</CardDescription>
      </CardHeader>
      <CardContent>
        {hasData ? (
          <ReactECharts
            option={option}
            style={{ height, width: "100%" }}
            opts={{ renderer: "canvas" }}
            notMerge
            lazyUpdate
          />
        ) : (
          <div
            className="flex items-center justify-center rounded-md border border-dashed text-sm text-muted-foreground"
            style={{ height }}
          >
            暂无现金流数据
          </div>
        )}
      </CardContent>
    </Card>
  );
}
