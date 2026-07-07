/**
 * T06: 策略表格（领域内全部策略列表）。
 */
"use client";

import Link from "next/link";
import type { StrategySummary } from "@/types/api";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import {
  formatNumber,
  formatPercent,
  returnColorClass,
} from "@/lib/utils";

export interface StrategyTableProps {
  items: StrategySummary[];
  loading?: boolean;
}

export function StrategyTable({ items }: StrategyTableProps) {
  return (
    <div className="rounded-lg border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>策略 ID</TableHead>
            <TableHead>领域</TableHead>
            <TableHead className="text-right">综合得分</TableHead>
            <TableHead className="text-right">年化收益</TableHead>
            <TableHead className="text-right">夏普</TableHead>
            <TableHead className="text-right">最大回撤</TableHead>
            <TableHead>状态</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.length === 0 ? (
            <TableRow>
              <TableCell
                colSpan={7}
                className="py-8 text-center text-muted-foreground"
              >
                暂无策略
              </TableCell>
            </TableRow>
          ) : (
            items.map((s) => (
              <TableRow key={s.strategy_id}>
                <TableCell>
                  <Link
                    href={`/strategies/${s.strategy_id}`}
                    className="font-medium text-primary hover:underline"
                  >
                    {s.strategy_id}
                  </Link>
                  <div className="text-xs text-muted-foreground">
                    {s.prototype_id}
                  </div>
                </TableCell>
                <TableCell>{s.domain}</TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatNumber(s.composite_score ?? null, 2)}
                </TableCell>
                <TableCell
                  className={`text-right tabular-nums ${returnColorClass(
                    s.annual_return ?? null,
                  )}`}
                >
                  {formatPercent(s.annual_return ?? null)}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatNumber(s.sharpe ?? null, 2)}
                </TableCell>
                <TableCell className="text-right tabular-nums text-down">
                  {formatPercent(s.max_drawdown ?? null)}
                </TableCell>
                <TableCell>
                  {s.adopted ? (
                    <Badge variant="success">已采用</Badge>
                  ) : s.disabled ? (
                    <Badge variant="danger">已停用</Badge>
                  ) : (
                    <Badge variant="secondary">候选</Badge>
                  )}
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}
