/**
 * T09: ECharts 现金流时序图。
 * 份额变动柱状（正绿负红）+ 机构持有折线（双 Y 轴）。
 */
"use client";

import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { Cashflow, StrategyCashflow } from "@/types/api";

export interface CashflowChartProps {
  data: Cashflow | StrategyCashflow | null | undefined;
  height?: number;
}

export function CashflowChart({ data, height = 320 }: CashflowChartProps) {
  const option = useMemo(() => {
    const dates = (data?.dates as string[]) ?? [];
    const shareChange = (data?.share_change as number[]) ?? [];
    const institution = (data?.institution_holding as number[]) ?? [];
    return {
      animation: false,
      grid: { left: 56, right: 56, top: 40, bottom: 56 },
      tooltip: {
        trigger: "axis" as const,
        axisPointer: { type: "shadow" as const },
      },
      legend: {
        data: ["份额变动", "机构持有"],
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
      yAxis: [
        {
          type: "value" as const,
          name: "份额变动",
          axisLabel: {
            color: "#64748b",
            fontSize: 11,
            formatter: (v: number) =>
              Math.abs(v) >= 1e8
                ? `${(v / 1e8).toFixed(1)}亿`
                : v.toFixed(0),
          },
          splitLine: { lineStyle: { color: "#f1f5f9" } },
        },
        {
          type: "value" as const,
          name: "机构持有%",
          axisLabel: {
            color: "#64748b",
            fontSize: 11,
            formatter: (v: number) => `${v.toFixed(1)}%`,
          },
          splitLine: { show: false },
        },
      ],
      dataZoom:
        dates.length > 30
          ? [{ type: "inside" as const }, { type: "slider" as const, height: 18, bottom: 8 }]
          : [],
      series: [
        {
          name: "份额变动",
          type: "bar" as const,
          data: shareChange.map((v) => ({
            value: v,
            // 正绿负红（A 股惯例）
            itemStyle: { color: v >= 0 ? "#10B981" : "#EF4444" },
          })),
          barMaxWidth: 28,
        },
        {
          name: "机构持有",
          type: "line" as const,
          yAxisIndex: 1,
          data: institution,
          showSymbol: false,
          smooth: true,
          lineStyle: { width: 2, color: "#6366f1" },
          sampling: "lttb" as const,
        },
      ],
    };
  }, [data]);

  if (
    !data ||
    ((data?.dates as string[] | undefined)?.length ?? 0) === 0
  ) {
    return (
      <div
        className="flex items-center justify-center rounded-md border border-dashed text-sm text-muted-foreground"
        style={{ height }}
      >
        暂无现金流数据
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

export default CashflowChart;
