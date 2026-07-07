/**
 * T04: 全局错误边界。
 * 捕获子组件渲染异常，展示友好提示 + 重试按钮。
 */
"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props {
  children: ReactNode;
  fallback?: (error: Error, reset: () => void) => ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // 本地工具，仅 console；生产可接 Sentry
    // eslint-disable-next-line no-console
    console.error("[ErrorBoundary]", error, info);
  }

  reset = () => this.setState({ error: null });

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    if (this.props.fallback) return this.props.fallback(error, this.reset);
    return (
      <div className="flex min-h-[200px] flex-col items-center justify-center gap-3 rounded-lg border border-dashed p-8 text-center">
        <AlertTriangle className="h-8 w-8 text-warn" />
        <div className="text-base font-medium">页面出错了</div>
        <div className="max-w-md text-sm text-muted-foreground">
          {error.message || "未知错误"}
        </div>
        <Button variant="outline" size="sm" onClick={this.reset}>
          <RotateCcw className="mr-1 h-3.5 w-3.5" /> 重试
        </Button>
      </div>
    );
  }
}
