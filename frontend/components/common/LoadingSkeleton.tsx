/**
 * T04: 通用 Loading 骨架屏。
 * 提供几种常用形态：卡片、表格、列表。
 */
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

/** 卡片骨架（KPI 用） */
export function CardSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("rounded-lg border p-5", className)}>
      <Skeleton className="h-4 w-24" />
      <Skeleton className="mt-3 h-8 w-32" />
      <Skeleton className="mt-2 h-3 w-20" />
    </div>
  );
}

/** 行骨架 */
export function RowSkeleton({ cols = 5 }: { cols?: number }) {
  return (
    <div className="flex items-center gap-3 px-3 py-3">
      {Array.from({ length: cols }).map((_, i) => (
        <Skeleton key={i} className="h-4 flex-1" />
      ))}
    </div>
  );
}

/** 表格骨架 */
export function TableSkeleton({
  rows = 5,
  cols = 5,
  className,
}: {
  rows?: number;
  cols?: number;
  className?: string;
}) {
  return (
    <div className={cn("rounded-lg border", className)}>
      {Array.from({ length: rows }).map((_, r) => (
        <RowSkeleton key={r} cols={cols} />
      ))}
    </div>
  );
}

/** 列表骨架 */
export function ListSkeleton({ items = 3 }: { items?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: items }).map((_, i) => (
        <div key={i} className="flex items-center gap-3">
          <Skeleton className="h-10 w-10 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3 w-1/3" />
            <Skeleton className="h-3 w-1/2" />
          </div>
        </div>
      ))}
    </div>
  );
}

/** 图表骨架 */
export function ChartSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("rounded-lg border p-5", className)}>
      <Skeleton className="h-4 w-32" />
      <Skeleton className="mt-4 h-[280px] w-full" />
    </div>
  );
}

/** 全页加载骨架 */
export function PageSkeleton() {
  return (
    <div className="space-y-4 p-6">
      <Skeleton className="h-7 w-48" />
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <CardSkeleton />
        <CardSkeleton />
        <CardSkeleton />
      </div>
      <TableSkeleton />
    </div>
  );
}
