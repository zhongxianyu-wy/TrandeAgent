/**
 * T11: 持仓行业雷达图（前 N 行业占比）。
 */
"use client";

import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import { Boxes } from "lucide-react";
import type { Holdings } from "@/types/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export interface HoldingsRadarProps {
  holdings: Holdings | null | undefined;
  height?: number;
}

export function HoldingsRadar({ holdings, height = 320 }: HoldingsRadarProps) {
  const option = useMemo(() => {
    const inds = (holdings?.industries ?? [])
      .slice(0, 8)
      .map((i) => ({
        name: String(i.industry ?? ""),
        value: Number(i.weight ?? 0),
      }));
    return {
      tooltip: {},
      radar: {
        indicator: inds.map((i) => ({
          name: i.name,
          max: Math.max(0.5, ...inds.map((x) => x.value)),
        })),
        axisName: { color: "#64748b", fontSize: 11 },
        splitArea: {
          areaStyle: { color: ["#fff", "#f8fafc"] },
        },
      },
      series: [
        {
          type: "radar" as const,
          data: [
            {
              value: inds.map((i) => i.value),
              name: "行业占比",
              areaStyle: { color: "rgba(37,99,235,0.18)" },
              lineStyle: { color: "#2563eb" },
              itemStyle: { color: "#2563eb" },
            },
          ],
        },
      ],
    };
  }, [holdings]);

  const hasData =
    (holdings?.industries?.length ?? 0) > 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Boxes className="h-4 w-4" /> 持仓行业雷达
        </CardTitle>
        <CardDescription>前 {Math.min(8, holdings?.industries?.length ?? 0)} 行业占比</CardDescription>
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
            暂无持仓行业数据
          </div>
        )}
      </CardContent>
    </Card>
  );
}
