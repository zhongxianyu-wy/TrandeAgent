/**
 * T03: 顶部顶栏（数据新鲜度 + 快捷操作）。
 */
"use client";

import { useQuery } from "@tanstack/react-query";
import { RefreshCw, Activity, Database } from "lucide-react";
import { apiGet } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type { SystemStatus } from "@/types/api";
import { Badge } from "@/components/ui/badge";
import { formatNumber } from "@/lib/utils";

/** 数据新鲜度指示器 */
export function FreshnessIndicator() {
  const { data, isLoading } = useQuery({
    queryKey: queryKeys.system.status(),
    queryFn: () => apiGet<SystemStatus>("/api/system/status"),
    refetchInterval: 60 * 1000,
  });

  if (isLoading || !data) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <RefreshCw className="h-3.5 w-3.5 animate-spin" /> 加载中…
      </div>
    );
  }

  const fresh = data.data_freshness;
  const total = fresh?.total ?? 0;
  const stale = fresh?.stale ?? 0;
  const isStale = stale > 0;

  return (
    <div className="flex items-center gap-3">
      <div className="flex items-center gap-1.5 text-sm">
        <Database
          className={`h-3.5 w-3.5 ${
            isStale ? "text-warn" : "text-up"
          }`}
        />
        <span className="text-muted-foreground">数据</span>
        <span className="font-medium">{formatNumber(total, 0)} 只</span>
        {isStale ? (
          <Badge variant="warn" className="ml-1">
            {formatNumber(stale, 0)} 待更新
          </Badge>
        ) : (
          <Badge variant="success" className="ml-1">
            最新
          </Badge>
        )}
      </div>
      <div className="hidden items-center gap-1.5 text-sm text-muted-foreground sm:flex">
        <Activity className="h-3.5 w-3.5" />
        活跃任务 <span className="font-medium">{data.active_jobs}</span>
      </div>
    </div>
  );
}

/** 顶栏 */
export function Topbar() {
  return (
    <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b bg-card/80 px-6 backdrop-blur">
      <FreshnessIndicator />
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span>观察池 {""}</span>
        <PoolSize />
      </div>
    </header>
  );
}

/** 观察池规模（顶栏右侧小指示） */
function PoolSize() {
  const { data } = useQuery({
    queryKey: queryKeys.system.status(),
    queryFn: () => apiGet<SystemStatus>("/api/system/status"),
  });
  return <span className="font-medium">{data?.observation_pool_size ?? 0}</span>;
}
