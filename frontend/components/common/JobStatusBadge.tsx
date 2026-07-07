/**
 * T17: 任务状态徽标（管理台 + 任务监控共用）。
 */
"use client";

import { Badge } from "@/components/ui/badge";

export function JobStatusBadge({ status }: { status: string }) {
  if (status === "succeeded")
    return <Badge variant="success">成功</Badge>;
  if (status === "failed") return <Badge variant="danger">失败</Badge>;
  if (status === "running")
    return <Badge variant="warn">运行中</Badge>;
  return <Badge variant="secondary">等待</Badge>;
}
