/**
 * T16: YAML 规则表单化编辑 + 影响范围预览。
 * 不手写 YAML，用 react-hook-form + zod 结构化表单。
 * 保存前调 PUT /api/config 返回 ChangeImpact，显示"影响 N 只基金"。
 */
"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Save, AlertTriangle, GitCommit, Undo2 } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPost, apiPut } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type {
  AppConfig,
  ChangeImpact,
  ConfigHistory,
  ConfigUpdateResult,
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
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { ConfirmModal } from "@/components/common/ConfirmModal";
import {
  TableSkeleton,
  ListSkeleton,
} from "@/components/common/LoadingSkeleton";

// 配置 schema（简化：聚焦观察池 + 信号规则文本）
const configSchema = z.object({
  observation_pool: z.array(z.string()).default([]),
  signal_rules_text: z.string().default(""),
});

type ConfigForm = z.infer<typeof configSchema>;

export default function ConfigEditPage() {
  const qc = useQueryClient();
  const [impact, setImpact] = useState<ConfigUpdateResult | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const pendingValues = useRef<ConfigForm | null>(null);

  const cfgQ = useQuery({
    queryKey: queryKeys.config.current(),
    queryFn: () => apiGet<AppConfig>("/api/config"),
  });

  const historyQ = useQuery({
    queryKey: queryKeys.config.history(),
    queryFn: () => apiGet<ConfigHistory>("/api/config/history"),
  });

  const form = useForm<ConfigForm>({
    resolver: zodResolver(configSchema),
    defaultValues: { observation_pool: [], signal_rules_text: "" },
  });

  // 加载后回填
  useEffect(() => {
    if (cfgQ.data) {
      const cfg = cfgQ.data;
      const rules = cfg.signal_rules ?? [];
      form.reset({
        observation_pool: cfg.observation_pool ?? [],
        signal_rules_text:
          typeof rules === "string"
            ? rules
            : JSON.stringify(rules, null, 2),
      });
    }
  }, [cfgQ.data, form]);

  const saveM = useMutation({
    mutationFn: async (values: ConfigForm) => {
      // 构造提交 payload：尝试把 signal_rules_text 解析为 JSON，失败则保留字符串
      let signal_rules: unknown = values.signal_rules_text;
      const text = values.signal_rules_text.trim();
      if (text) {
        try {
          signal_rules = JSON.parse(text);
        } catch {
          signal_rules = text;
        }
      }
      const payload: AppConfig = {
        ...cfgQ.data,
        observation_pool: values.observation_pool.filter(Boolean),
        signal_rules: signal_rules as unknown[],
      };
      // 后端 PUT 会做保存 + commit + 影响范围分析
      return apiPut<ConfigUpdateResult>("/api/config", payload);
    },
    onSuccess: (data) => {
      setImpact(data);
      toast.success(`已保存，影响 ${data.affected_count} 只基金`);
      qc.invalidateQueries({ queryKey: queryKeys.config.all });
    },
    onError: (e: unknown) =>
      toast.error(`保存失败：${e instanceof Error ? e.message : "未知"}`),
  });

  const onSubmit = (values: ConfigForm) => {
    pendingValues.current = values;
    setConfirmOpen(true);
  };

  // 回滚到指定 commit
  const rollbackM = useMutation({
    mutationFn: (commit: string) =>
      apiPost<ConfigUpdateResult>(`/api/config/rollback/${commit}`),
    onSuccess: (data) => {
      toast.success(`已回滚，影响 ${data.affected_count} 只基金`);
      qc.invalidateQueries({ queryKey: queryKeys.config.all });
    },
    onError: (e: unknown) =>
      toast.error(`回滚失败：${e instanceof Error ? e.message : "未知"}`),
  });

  const [rollbackCommit, setRollbackCommit] = useState<string | null>(null);

  const observationPool = form.watch("observation_pool");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">规则配置</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          结构化表单编辑（无需手写 YAML），保存自动 git commit
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* 表单 */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>编辑配置</CardTitle>
            <CardDescription>
              观察池 + 信号规则（规则支持 JSON 数组）
            </CardDescription>
          </CardHeader>
          <CardContent>
            {cfgQ.isLoading ? (
              <TableSkeleton rows={6} cols={2} />
            ) : (
              <form
                onSubmit={form.handleSubmit(onSubmit)}
                className="space-y-4"
              >
                <div className="space-y-1.5">
                  <Label htmlFor="pool">观察池（逗号分隔基金代码）</Label>
                  <Input
                    id="pool"
                    placeholder="000001,110011"
                    value={observationPool.join(",")}
                    onChange={(e) =>
                      form.setValue(
                        "observation_pool",
                        e.target.value
                          .split(/[,\s]+/)
                          .filter(Boolean),
                      )
                    }
                  />
                  <p className="text-xs text-muted-foreground">
                    当前 {observationPool.length} 只
                  </p>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="rules">信号规则（JSON）</Label>
                  <Textarea
                    id="rules"
                    rows={10}
                    className="font-mono text-xs"
                    placeholder='[{"type":"ma_cross","fast":5,"slow":20}]'
                    {...form.register("signal_rules_text")}
                  />
                </div>

                <div className="flex items-center gap-2">
                  <Button type="submit" disabled={saveM.isPending}>
                    <Save className="mr-1 h-3.5 w-3.5" />
                    {saveM.isPending ? "保存中…" : "保存并预览影响"}
                  </Button>
                  <span className="text-xs text-muted-foreground">
                    保存后自动 git commit
                  </span>
                </div>
              </form>
            )}
          </CardContent>
        </Card>

        {/* 影响范围 + 历史 */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-warn" /> 影响范围
              </CardTitle>
              <CardDescription>
                最近一次保存的变更影响
              </CardDescription>
            </CardHeader>
            <CardContent>
              {!impact ? (
                <div className="py-4 text-center text-sm text-muted-foreground">
                  保存后显示影响范围
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="text-2xl font-semibold tabular-nums">
                    影响{" "}
                    <span className="text-warn">
                      {impact.affected_count}
                    </span>{" "}
                    只基金
                  </div>
                  {impact.impacts.map((im: ChangeImpact, i) => (
                    <div key={i} className="rounded-md border p-2 text-xs">
                      <div className="font-medium">{im.field}</div>
                      <div className="text-muted-foreground">
                        {(im.affected_funds ?? []).slice(0, 5).join(", ")}
                        {(im.affected_funds ?? []).length > 5
                          ? ` 等 ${(im.affected_funds ?? []).length} 只`
                          : ""}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <GitCommit className="h-4 w-4" /> 版本历史
              </CardTitle>
              <CardDescription>最近 10 次提交</CardDescription>
            </CardHeader>
            <CardContent>
              {historyQ.isLoading ? (
                <ListSkeleton items={5} />
              ) : (historyQ.data?.history?.length ?? 0) === 0 ? (
                <div className="py-4 text-center text-sm text-muted-foreground">
                  暂无历史
                </div>
              ) : (
                <ol className="space-y-2 text-xs">
                  {historyQ.data?.history.map((h) => (
                    <li
                      key={h.commit}
                      className="flex items-start justify-between gap-2"
                    >
                      <div className="min-w-0">
                        <div className="truncate font-mono text-muted-foreground">
                          {h.commit.slice(0, 8)}
                        </div>
                        <div className="truncate">{h.message}</div>
                      </div>
                      <div className="flex shrink-0 items-center gap-1">
                        <Badge variant="outline">{h.date}</Badge>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-6 px-2 text-xs"
                          disabled={rollbackM.isPending}
                          onClick={() => setRollbackCommit(h.commit)}
                          title={`回滚到 ${h.commit.slice(0, 8)}`}
                        >
                          <Undo2 className="mr-1 h-3 w-3" />
                          回滚
                        </Button>
                      </div>
                    </li>
                  ))}
                </ol>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <ConfirmModal
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title="确认保存配置"
        description="保存将自动创建 git commit 并重新计算影响范围，确定继续？"
        confirmText="确认保存"
        loading={saveM.isPending}
        onConfirm={async () => {
          setConfirmOpen(false);
          if (pendingValues.current) {
            await saveM.mutateAsync(pendingValues.current);
          }
        }}
      />

      <ConfirmModal
        open={rollbackCommit !== null}
        onOpenChange={(v) => !v && setRollbackCommit(null)}
        title="确认回滚配置"
        description={`将回滚到 ${rollbackCommit?.slice(0, 8) ?? ""}，当前未保存的修改会丢失，确定继续？`}
        confirmText="确认回滚"
        loading={rollbackM.isPending}
        onConfirm={async () => {
          const c = rollbackCommit;
          setRollbackCommit(null);
          if (c) {
            await rollbackM.mutateAsync(c);
          }
        }}
      />
    </div>
  );
}
