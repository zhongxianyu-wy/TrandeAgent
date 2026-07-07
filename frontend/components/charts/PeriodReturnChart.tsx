/**
 * T07: ECharts 多周期收益率柱状图。
 * 收益 vs 基准双柱，A 股配色（正绿负红）。
 */
"use client";

import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { PeriodReturn } from "@/types/api";

export interface PeriodReturnChartProps {
  data: PeriodReturn | null | undefined;
  height?: number;
  /** 单位："percent" 收益率，"value" 普通数值 */
  unit?: "percent" | "value";
}

export function PeriodReturnChart({
  data,
  height = 320,
  unit = "percent",
}: PeriodReturnChartProps) {
  const option = useMemo(() => {
    const labels = data?.labels ?? [];
    const returns = data?.returns ?? [];
    const bench = data?.benchmark_returns ?? [];
    return {
      animation: false,
      grid: { left: 48, right: 16, top: 40, bottom: 56 },
      tooltip: {
        trigger: "axis" as const,
        axisPointer: { type: "shadow" as const },
        valueFormatter: (v: number) =>
          unit === "percent" ? `${(v * 100).toFixed(2)}%` : v?.toFixed(2),
      },
      legend: {
        data: ["本策略", "基准"],
        top: 4,
        right: 8,
        textStyle: { color: "#64748b" },
      },
      xAxis: {
        type: "category" as const,
        data: labels,
        axisLabel: { color: "#64748b", fontSize: 11 },
        axisLine: { lineStyle: { color: "#e5e5e5" } },
      },
      yAxis: {
        type: "value" as const,
        axisLabel: {
          color: "#64748b",
          fontSize: 11,
          formatter: (v: number) =>
            unit === "percent" ? `${(v * 100).toFixed(1)}%` : v.toFixed(2),
        },
        splitLine: { lineStyle: { color: "#f1f5f9" } },
      },
      // 大数据采样优化
      dataZoom: labels.length > 30 ? [{ type: "inside" as const }, { type: "slider" as const, height: 18, bottom: 8 }] : [],
      series: [
        {
          name: "本策略",
          type: "bar" as const,
          data: returns.map((v) => ({
            value: v,
            // 正绿负红（A 股惯例）
            itemStyle: { color: v >= 0 ? "#10B981" : "#EF4444" },
          })),
          barMaxWidth: 24,
        },
        {
          name: "基准",
          type: "bar" as const,
          data: bench,
          barMaxWidth: 24,
          itemStyle: { color: "#94a3b8" },
        },
      ],
    };
  }, [data, unit]);

  if (!data || (data.labels?.length ?? 0) === 0) {
    return (
      <div
        className="flex items-center justify-center rounded-md border border-dashed text-sm text-muted-foreground"
        style={{ height }}
      >
        暂无周期数据
      </div>
    );
  }

  return (
    <ReactECharts
      option={option}
      style={{ height, width: "100%" }}
      opts={{ renderer: "canvas" }}
      notMerge
      lazyUpdate
    />
  );
}
