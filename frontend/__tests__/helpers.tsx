/**
 * T18: 测试用 QueryClient 帮助函数。
 * 关闭 retry 与不必要的 console 输出。
 */
import React, { type ReactNode } from "react";
import {
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";

export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

export function withQueryClient(
  client: QueryClient,
  children: ReactNode,
) {
  return React.createElement(
    QueryClientProvider,
    { client },
    children,
  );
}
