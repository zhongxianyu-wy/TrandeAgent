/**
 * T03: 根布局（侧边栏 + 顶栏 + Providers + Toaster + ErrorBoundary）。
 */
import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";
import { Toaster } from "@/components/ui/sonner";
import { ErrorBoundary } from "@/components/common/ErrorBoundary";

export const metadata: Metadata = {
  title: "TrandeAgent · 基金投资助手",
  description: "本地基金投资分析与策略管理工具",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body className="min-h-screen bg-background">
        <Providers>
          <ErrorBoundary>
            <div className="flex min-h-screen">
              <Sidebar />
              <div className="flex flex-1 flex-col md:pl-60">
                <Topbar />
                <main className="flex-1 p-6">{children}</main>
              </div>
            </div>
          </ErrorBoundary>
          <Toaster position="top-right" richColors />
        </Providers>
      </body>
    </html>
  );
}
