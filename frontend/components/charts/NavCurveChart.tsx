/**
 * T08: ECharts 净值曲线 + 回撤阴影 + 基准对比。
 * - 净值主线（蓝）
 * - 回撤面积（红，负值）
 * - 基准虚线（灰）
 * - dataZoom 缩放（大数据）
 */
"use client";

import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { NavCurve } from "@/types/api";

export interface NavCurveChartProps {
  data: NavCurve | null | undefined;
  height?: number;
}

export function NavCurveChart({ data, height = 420 }: NavCurveChartProps) {
  const option = useMemo(() => {
    const dates = data?.dates ?? [];
    const nav = data?.nav ?? [];
    const drawdown = data?.drawdown ?? [];
    const bench = data?.benchmark_nav ?? [];
    const large = dates.length > 800;
    return {
      animation: false,
      grid: { left: 48, right: 24, top: 40, bottom: 72 },
      tooltip: {
        trigger: "axis" as const,
        axisPointer: { type: "cross" as const },
        valueFormatter: (v: number) =>
          v == null ? "—" : v.toFixed(4),
      },
      legend: {
        data: ["净值", "回撤", "基准"],
        top: 4,
        right: 8,
        textStyle: { color: "#64748b" },
      },
      xAxis: {
        type: "category" as const,
        data: dates,
        boundaryGap: false,
        axisLabel: { color: "#64748b", fontSize: 11 },
        axisLine: { lineStyle: { color: "#e5e5e5" } },
      },
      yAxis: [
        {
          type: "value" as const,
          name: "净值",
          scale: true,
          axisLabel: { color: "#64748b", fontSize: 11 },
          splitLine: { lineStyle: { color: "#f1f5f9" } },
        },
        {
          type: "value" as const,
          name: "回撤",
          axisLabel: {
            color: "#ef4444",
            fontSize: 11,
            formatter: (v: number) => `${(v * 100).toFixed(1)}%`,
          },
          splitLine: { show: false },
        },
      ],
      // 大数据采样优化：5 年日频 ~1200 点
      dataZoom: large
        ? [
            { type: "inside" as const },
            {
              type: "slider" as const,
              height: 22,
              bottom: 12,
              brushSelect: false,
            },
          ]
        : [{ type: "inside" as const }],
      series: [
        {
          name: "净值",
          type: "line" as const,
          data: nav,
          showSymbol: false,
          smooth: false,
          lineStyle: { width: 2, color: "#2563eb" },
          sampling: "lttb" as const,
          large,
        },
        {
          name: "回撤",
          type: "line" as const,
          yAxisIndex: 1,
          data: drawdown,
          showSymbol: false,
          smooth: true,
          areaStyle: { color: "rgba(239,68,68,0.18)" },
          lineStyle: { width: 1, color: "#ef4444" },
          sampling: "lttb" as const,
        },
        {
          name: "基准",
          type: "line" as const,
          data: bench,
          showSymbol: false,
          smooth: false,
          lineStyle: {
            width: 1.5,
            color: "#94a3b8",
            type: "dashed" as const,
          },
          sampling: "lttb" as const,
        },
      ],
    };
  }, [data]);

  if (!data || (data.dates?.length ?? 0) === 0) {
    return (
      <div
        className="flex items-center justify-center rounded-md border border-dashed text-sm text-muted-foreground"
        style={{ height }}
      >
        暂无净值数据
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

export default NavCurveChart;
