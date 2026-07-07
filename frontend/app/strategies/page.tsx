/**
 * T06: 策略池总览页 `/strategies`。
 * - 8 领域 tab 切换
 * - 每领域 Top-5 卡片 + 全部策略表格
 * - 排序：综合得分/收益/夏普/回撤
 */
"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type { PaginatedData, StrategySummary } from "@/types/api";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { StrategyCard } from "@/components/strategy/StrategyCard";
import { StrategyTable } from "@/components/strategy/StrategyTable";
import { CardSkeleton, TableSkeleton } from "@/components/common/LoadingSkeleton";

const DOMAINS = [
  "价值",
  "成长",
  "红利",
  "趋势",
  "逆向",
  "全球配置",
  "指数增强",
  "低波",
] as const;

const SORTS: { value: string; label: string }[] = [
  { value: "score", label: "综合得分" },
  { value: "return", label: "年化收益" },
  { value: "sharpe", label: "夏普" },
  { value: "drawdown", label: "最大回撤" },
];

export default function StrategiesPage() {
  const [domain, setDomain] = useState<string>("价值");
  const [sort, setSort] = useState<string>("score");

  const listQ = useQuery({
    queryKey: queryKeys.strategies.list({ domain, sort, size: 100 }),
    queryFn: () =>
      apiGet<PaginatedData<StrategySummary>>("/api/strategies", {
        domain,
        sort,
        size: 100,
      }),
  });

  const items = listQ.data?.items ?? [];
  const top5 = items.slice(0, 5);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">策略池</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            按 8 投资领域分组，对比策略表现
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">排序</span>
          <Select value={sort} onValueChange={setSort}>
            <SelectTrigger className="w-36">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {SORTS.map((s) => (
                <SelectItem key={s.value} value={s.value}>
                  {s.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <Tabs value={domain} onValueChange={setDomain}>
        <TabsList className="flex w-full flex-wrap justify-start">
          {DOMAINS.map((d) => (
            <TabsTrigger key={d} value={d}>
              {d}
            </TabsTrigger>
          ))}
        </TabsList>

        {/* 仅渲染当前激活领域的内容，避免重复加载 8 个领域 */}
        <TabsContent value={domain} forceMount>
          <div className="space-y-6">
            <section>
              <h2 className="mb-3 text-sm font-medium text-muted-foreground">
                Top-5 卡片
              </h2>
              {listQ.isLoading ? (
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
                  <CardSkeleton />
                  <CardSkeleton />
                  <CardSkeleton />
                </div>
              ) : top5.length === 0 ? (
                <div className="rounded-lg border border-dashed py-8 text-center text-sm text-muted-foreground">
                  暂无策略
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
                  {top5.map((s) => (
                    <StrategyCard key={s.strategy_id} s={s} />
                  ))}
                </div>
              )}
            </section>

            <section>
              <h2 className="mb-3 text-sm font-medium text-muted-foreground">
                全部策略（共 {items.length} 个）
              </h2>
              {listQ.isLoading ? (
                <TableSkeleton rows={8} cols={7} />
              ) : (
                <StrategyTable items={items} />
              )}
            </section>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
