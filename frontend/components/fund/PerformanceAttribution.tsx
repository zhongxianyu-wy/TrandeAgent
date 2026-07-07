/**
 * T12: 业绩归因对比表（本基金 / 同类平均 / 沪深300）。
 */
"use client";

import { BarChart3 } from "lucide-react";
import type { PerformanceAttribution } from "@/types/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatPercent, returnColorClass } from "@/lib/utils";

export interface PerformanceAttributionProps {
  data: PerformanceAttribution | null | undefined;
}

export function PerformanceAttributionTable({
  data,
}: PerformanceAttributionProps) {
  const metrics = data?.metrics ?? [];
  const fund = data?.fund ?? [];
  const peer = data?.peer_avg ?? [];
  const hs300 = data?.hs300;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <BarChart3 className="h-4 w-4" /> 业绩归因对比
        </CardTitle>
        <CardDescription>本基金 / 同类平均 / 沪深300</CardDescription>
      </CardHeader>
      <CardContent>
        {metrics.length === 0 ? (
          <div className="py-6 text-center text-sm text-muted-foreground">
            暂无归因数据
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>指标</TableHead>
                <TableHead className="text-right">本基金</TableHead>
                <TableHead className="text-right">同类平均</TableHead>
                {hs300 ? (
                  <TableHead className="text-right">沪深300</TableHead>
                ) : null}
              </TableRow>
            </TableHeader>
            <TableBody>
              {metrics.map((m, i) => (
                <TableRow key={m}>
                  <TableCell className="font-medium">{m}</TableCell>
                  <TableCell
                    className={`text-right tabular-nums ${returnColorClass(
                      fund[i],
                    )}`}
                  >
                    {formatPercent(fund[i])}
                  </TableCell>
                  <TableCell className="text-right tabular-nums text-muted-foreground">
                    {formatPercent(peer[i])}
                  </TableCell>
                  {hs300 ? (
                    <TableCell className="text-right tabular-nums text-muted-foreground">
                      {formatPercent(hs300[i])}
                    </TableCell>
                  ) : null}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
