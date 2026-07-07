/**
 * T13: LLM 报告（富文本渲染 + 【依据】可点击 + JSON 原文可折叠）。
 */
"use client";

import { useState } from "react";
import { FileText, ChevronDown, Link2 } from "lucide-react";
import { toast } from "sonner";
import type { LlmReport } from "@/types/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export interface LlmReportProps {
  data: LlmReport | null | undefined;
  loading?: boolean;
}

/** 极简 Markdown 渲染：标题/段落/列表/加粗/【依据】锚点 */
function renderMarkdown(md: string, references?: LlmReport["references"]) {
  const lines = md.split("\n");
  const refs = references ?? [];
  return lines.map((line, i) => {
    // 标题
    if (line.startsWith("### ")) {
      return (
        <h4 key={i} className="mt-3 text-sm font-semibold">
          {inline(line.slice(4), refs)}
        </h4>
      );
    }
    if (line.startsWith("## ")) {
      return (
        <h3 key={i} className="mt-4 text-base font-semibold">
          {inline(line.slice(3), refs)}
        </h3>
      );
    }
    if (line.startsWith("# ")) {
      return (
        <h2 key={i} className="mt-4 text-lg font-semibold">
          {inline(line.slice(2), refs)}
        </h2>
      );
    }
    // 列表
    if (/^\s*[-*]\s+/.test(line)) {
      return (
        <li key={i} className="ml-4 list-disc">
          {inline(line.replace(/^\s*[-*]\s+/, ""), refs)}
        </li>
      );
    }
    // 空行
    if (line.trim() === "") return <div key={i} className="h-2" />;
    // 段落
    return (
      <p key={i} className="leading-relaxed">
        {inline(line, refs)}
      </p>
    );
  });
}

/** 行内：**加粗** 和【依据】锚点 */
function inline(text: string, references: LlmReport["references"]) {
  const refs = references ?? [];
  const parts: React.ReactNode[] = [];
  const regex = /(\*\*[^*]+\*\*|【[^】]+】)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let idx = 0;
  while ((m = regex.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) {
      parts.push(
        <strong key={`b-${idx}`} className="font-semibold">
          {tok.slice(2, -2)}
        </strong>,
      );
    } else {
      // 【依据】锚点
      const label = tok.slice(1, -1);
      const ref = refs.find(
        (r) => r.label === label || r.anchor === label,
      );
      parts.push(
        <button
          key={`r-${idx}`}
          type="button"
          className="mx-0.5 inline-flex items-center gap-0.5 rounded bg-primary/10 px-1 text-xs text-primary hover:bg-primary/20"
          onClick={() =>
            ref
              ? toast.info(`查看依据：${ref.label}`)
              : toast.info(`查看依据：${label}`)
          }
        >
          <Link2 className="h-3 w-3" /> {label}
        </button>,
      );
    }
    last = m.index + tok.length;
    idx++;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

export function LlmReportCard({ data, loading }: LlmReportProps) {
  const [showJson, setShowJson] = useState(false);

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <div>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-4 w-4" /> LLM 分析报告
          </CardTitle>
          <CardDescription>AI 生成 · 含可点击依据</CardDescription>
        </div>
        {data?.json ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowJson((v) => !v)}
          >
            <ChevronDown
              className={`mr-1 h-3.5 w-3.5 transition-transform ${
                showJson ? "rotate-180" : ""
              }`}
            />
            JSON 原文
          </Button>
        ) : null}
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="py-6 text-center text-sm text-muted-foreground">
            报告加载中…
          </div>
        ) : !data?.markdown ? (
          <div className="py-6 text-center text-sm text-muted-foreground">
            暂无报告，可点击右上角"重新分析"
          </div>
        ) : (
          <>
            <div className="prose prose-sm max-w-none text-sm">
              {renderMarkdown(data.markdown, data.references)}
            </div>
            {showJson && data.json ? (
              <pre className="mt-4 max-h-80 overflow-auto rounded-md border bg-muted/30 p-3 text-xs">
                {JSON.stringify(data.json, null, 2)}
              </pre>
            ) : null}
          </>
        )}
      </CardContent>
    </Card>
  );
}
