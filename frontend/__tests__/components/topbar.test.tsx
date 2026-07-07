/**
 * T18: Topbar 组件测试（含 FreshnessIndicator 数据拉取）。
 */
import { describe, it, expect } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { Topbar } from "@/components/layout/Topbar";
import {
  createTestQueryClient,
  withQueryClient,
} from "@/__tests__/helpers";

function renderTopbar() {
  return render(
    withQueryClient(createTestQueryClient() as never, <Topbar />),
  );
}

describe("Topbar", () => {
  it("加载后渲染数据总数与待更新徽标", async () => {
    renderTopbar();
    // mock 返回 total=1200 stale=3
    await waitFor(() => {
      expect(screen.getByText(/1200/)).toBeInTheDocument();
    });
    expect(screen.getByText(/待更新/)).toBeInTheDocument();
  });

  it("渲染活跃任务数与观察池规模", async () => {
    renderTopbar();
    await waitFor(() => {
      // 活跃任务 1 + 观察池规模 5
      expect(screen.getByText("活跃任务")).toBeInTheDocument();
    });
    expect(screen.getByText("观察池")).toBeInTheDocument();
  });
});
