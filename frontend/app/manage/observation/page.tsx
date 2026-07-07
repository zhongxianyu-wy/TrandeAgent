/**
 * T17: 观察池管理 `/manage/observation`。
 * - 列表 + 增删
 * - 信号查看
 */
"use client";

import { useState } from "react";
import {
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import Link from "next/link";
import { Eye, Trash2, Plus, Signal as SignalIcon } from "lucide-react";
import { toast } from "sonner";
import { apiDelete, apiGet, apiPost } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type {
  ObservationPool,
  Signal,
} from "@/types/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ConfirmModal } from "@/components/common/ConfirmModal";
import {
  ListSkeleton,
  TableSkeleton,
} from "@/components/common/LoadingSkeleton";
import { signalColorClass } from "@/lib/utils";

export default function ObservationPage() {
  const qc = useQueryClient();
  const [newCode, setNewCode] = useState("");
  const [removeCode, setRemoveCode] = useState<string | null>(null);

  const poolQ = useQuery({
    queryKey: queryKeys.observation.all,
    queryFn: () => apiGet<ObservationPool>("/api/observation"),
  });

  const pool = poolQ.data?.pool ?? [];

  // 每只基金的信号并行查询
  const signalsQs = useQueries({
    queries: pool.map((code) => ({
      queryKey: queryKeys.observation.signals(code),
      queryFn: () =>
        apiGet<Signal[]>(`/api/observation/${code}/signals`),
      staleTime: 60 * 1000,
    })),
  });

  const addM = useMutation({
    mutationFn: (code: string) => apiPost(`/api/observation/${code}`),
    onSuccess: () => {
      toast.success("已加入观察池");
      setNewCode("");
      qc.invalidateQueries({ queryKey: queryKeys.observation.all });
    },
    onError: (e: unknown) =>
      toast.error(`加入失败：${e instanceof Error ? e.message : "未知"}`),
  });

  const removeM = useMutation({
    mutationFn: (code: string) => apiDelete(`/api/observation/${code}`),
    onSuccess: () => {
      toast.success("已移出观察池");
      setRemoveCode(null);
      qc.invalidateQueries({ queryKey: queryKeys.observation.all });
    },
    onError: (e: unknown) =>
      toast.error(`移出失败：${e instanceof Error ? e.message : "未知"}`),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">观察池管理</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          当前 {pool.length} 只 · 增删 + 信号查看
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Plus className="h-4 w-4" /> 加入观察池
          </CardTitle>
          <CardDescription>输入基金代码</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="flex items-center gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              const code = newCode.trim();
              if (code) addM.mutate(code);
            }}
          >
            <Input
              placeholder="如 000001"
              value={newCode}
              onChange={(e) => setNewCode(e.target.value)}
              className="max-w-xs"
            />
            <Button type="submit" disabled={addM.isPending || !newCode.trim()}>
              <Plus className="mr-1 h-3.5 w-3.5" /> 加入
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Eye className="h-4 w-4" /> 观察池列表
          </CardTitle>
          <CardDescription>含每只基金最新信号</CardDescription>
        </CardHeader>
        <CardContent>
          {poolQ.isLoading ? (
            <TableSkeleton rows={6} cols={4} />
          ) : pool.length === 0 ? (
            <div className="py-8 text-center text-sm text-muted-foreground">
              观察池为空
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>基金代码</TableHead>
                  <TableHead>最新信号</TableHead>
                  <TableHead>信号日期</TableHead>
                  <TableHead className="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pool.map((code, i) => {
                  const sigs = (signalsQs[i]?.data ?? []) as Signal[];
                  const latest = sigs[0];
                  return (
                    <TableRow key={code}>
                      <TableCell>
                        <Link
                          href={`/funds/${code}`}
                          className="font-medium text-primary hover:underline"
                        >
                          {code}
                        </Link>
                      </TableCell>
                      <TableCell>
                        {latest ? (
                          <Badge
                            variant="outline"
                            className={signalColorClass(
                              latest.signal_type,
                            )}
                          >
                            <SignalIcon className="mr-1 h-3 w-3" />
                            {latest.signal_type === "add"
                              ? "加仓"
                              : latest.signal_type === "reduce"
                                ? "减仓"
                                : latest.signal_type === "stop_loss"
                                  ? "止损"
                                  : latest.signal_type}
                          </Badge>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {latest?.date ?? "—"}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setRemoveCode(code)}
                        >
                          <Trash2 className="mr-1 h-3.5 w-3.5" /> 移出
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <ConfirmModal
        open={!!removeCode}
        onOpenChange={(o) => !o && setRemoveCode(null)}
        title="移出观察池"
        description={`确定将 ${removeCode} 移出观察池？`}
        destructive
        confirmText="移出"
        loading={removeM.isPending}
        onConfirm={() => {
          if (removeCode) removeM.mutate(removeCode);
        }}
      />
    </div>
  );
}
