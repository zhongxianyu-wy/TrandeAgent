/**
 * T03: 全局 Provider（TanStack Query）。
 * 所有页面 CSR，统一在客户端挂载 QueryClient。
 */
"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { useState, type ReactNode } from "react";

export function Providers({ children }: { children: ReactNode }) {
  // 每个客户端实例一个 QueryClient，避免 SSR 共享
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // 本地工具，可较激进缓存
            staleTime: 30 * 1000,
            gcTime: 5 * 60 * 1000,
            retry: 1,
            refetchOnWindowFocus: false,
          },
          mutations: { retry: 0 },
        },
      }),
  );

  return (
    <QueryClientProvider client={client}>
      {children}
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}
