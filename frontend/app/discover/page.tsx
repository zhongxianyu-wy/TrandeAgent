/**
 * T15: 发现页 `/discover`。
 * - 8 领域分组卡片
 * - 每领域 Top-5 推荐基金
 * - 每只基金附推荐理由
 * - 时间窗切换：今日/本周/本月
 * - 一键加入观察池
 */
"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { Eye, Compass } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPost } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type {
  DiscoverResult,
  DiscoverReasons,
  ObservationPool,
} from "@/types/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ListSkeleton } from "@/components/common/LoadingSkeleton";

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

const WINDOWS = [
  { value: "today", label: "今日" },
  { value: "week", label: "本周" },
  { value: "month", label: "本月" },
] as const;

export default function DiscoverPage() {
  const [window, setWindow] = useState<string>("today");
  const qc = useQueryClient();

  const discoverQ = useQuery({
    queryKey: queryKeys.discover.all(window),
    queryFn: () =>
      apiGet<DiscoverResult>("/api/discover", { window }),
  });

  const poolQ = useQuery({
    queryKey: queryKeys.observation.all,
    queryFn: () => apiGet<ObservationPool>("/api/observation"),
  });

  const addObsM = useMutation({
    mutationFn: (code: string) => apiPost(`/api/observation/${code}`),
    onSuccess: () => {
      toast.success("已加入观察池");
      qc.invalidateQueries({ queryKey: queryKeys.observation.all });
    },
    onError: (e: unknown) =>
      toast.error(`加入失败：${e instanceof Error ? e.message : "未知"}`),
  });

  const pool = poolQ.data?.pool ?? [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">发现</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            8 领域 × Top-5 推荐基金
          </p>
        </div>
        <Tabs value={window} onValueChange={setWindow}>
          <TabsList>
            {WINDOWS.map((w) => (
              <TabsTrigger key={w.value} value={w.value}>
                {w.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </div>

      {discoverQ.isLoading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Card key={i}>
              <CardHeader>
                <CardTitle>—</CardTitle>
              </CardHeader>
              <CardContent>
                <ListSkeleton items={5} />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
          {DOMAINS.map((d) => {
            const codes = discoverQ.data?.domains?.[d] ?? [];
            return (
              <Card key={d}>
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Compass className="h-4 w-4 text-primary" /> {d}
                  </CardTitle>
                  <CardDescription>Top-{Math.min(5, codes.length)}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-2 pt-0">
                  {codes.length === 0 ? (
                    <div className="py-4 text-center text-xs text-muted-foreground">
                      暂无推荐
                    </div>
                  ) : (
                    codes.map((code) => (
                      <DomainFundRow
                        key={code}
                        code={code}
                        inPool={pool.includes(code)}
                        onAdd={() => addObsM.mutate(code)}
                        adding={addObsM.isPending}
                      />
                    ))
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

function DomainFundRow({
  code,
  inPool,
  onAdd,
  adding,
}: {
  code: string;
  inPool: boolean;
  onAdd: () => void;
  adding: boolean;
}) {
  const reasonsQ = useQuery({
    queryKey: queryKeys.discover.reasons(code),
    queryFn: () => apiGet<DiscoverReasons>(`/api/discover/reasons/${code}`),
  });
  return (
    <div className="rounded-md border p-2">
      <div className="flex items-center justify-between">
        <Link
          href={`/funds/${code}`}
          className="font-medium text-primary hover:underline"
        >
          {code}
        </Link>
        {inPool ? (
          <Badge variant="success" className="gap-1 text-xs">
            <Eye className="h-3 w-3" /> 已观察
          </Badge>
        ) : (
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={onAdd}
            disabled={adding}
          >
            <Eye className="mr-1 h-3 w-3" /> 加观察
          </Button>
        )}
      </div>
      {reasonsQ.data?.reasons?.length ? (
        <ul className="mt-1 space-y-0.5 text-xs text-muted-foreground">
          {reasonsQ.data.reasons.slice(0, 2).map((r, i) => (
            <li key={i} className="truncate">
              · {r}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
