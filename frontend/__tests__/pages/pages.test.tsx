/**
 * T18: 页面集成测试（msw mock 全 API）。
 */
import { describe, it, expect, vi } from "vitest";

// mock echarts-for-react（页面包含图表）
vi.mock("echarts-for-react", () => ({
  __esModule: true,
  default: () => <div data-testid="echarts" />,
}));

// mock sonner.toast（避免在 jsdom 报错）
vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
  Toaster: () => null,
}));

import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient } from "@tanstack/react-query";
import {
  createTestQueryClient,
  withQueryClient,
} from "@/__tests__/helpers";
import DashboardPage from "@/app/page";
import StrategiesPage from "@/app/strategies/page";
import DiscoverPage from "@/app/discover/page";
import ManagePage from "@/app/manage/page";
import ObservationPage from "@/app/manage/observation/page";
import JobsPage from "@/app/manage/jobs/page";

// mock useParams / usePathname
vi.mock("next/navigation", () => ({
  useParams: () => ({ code: "000001", id: "strat-1" }),
  usePathname: () => "/",
}));

vi.mock("next/link", () => ({
  __esModule: true,
  default: ({
    children,
    href,
  }: {
    children: React.ReactNode;
    href: string;
  }) => (
    <a href={href} data-testid="link">
      {children}
    </a>
  ),
}));

function renderPage(page: React.ReactNode) {
  const client = createTestQueryClient() as unknown as QueryClient;
  return render(withQueryClient(client, page));
}

describe("首页 Dashboard", () => {
  it("渲染 KPI 与候选", async () => {
    renderPage(<DashboardPage />);
    expect(screen.getByText("今日总览")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("观察池规模")).toBeInTheDocument();
    });
  });
});

describe("策略池页", () => {
  it("渲染 8 领域 tab", async () => {
    renderPage(<StrategiesPage />);
    expect(screen.getByText("策略池")).toBeInTheDocument();
    expect(screen.getByText("价值")).toBeInTheDocument();
    expect(screen.getByText("指数增强")).toBeInTheDocument();
  });
});

describe("发现页", () => {
  it("渲染领域卡片", async () => {
    renderPage(<DiscoverPage />);
    expect(screen.getByText("发现")).toBeInTheDocument();
    await waitFor(() => {
      // mock discover 返回了 价值/成长/红利/趋势 4 个有数据领域
      expect(screen.getAllByText("价值").length).toBeGreaterThan(0);
    });
  });
});

describe("管理台首页", () => {
  it("渲染入口卡片", async () => {
    renderPage(<ManagePage />);
    expect(screen.getByText("管理台")).toBeInTheDocument();
    expect(screen.getByText("规则配置")).toBeInTheDocument();
    expect(screen.getByText("观察池管理")).toBeInTheDocument();
    expect(screen.getByText("任务监控")).toBeInTheDocument();
  });
});

describe("观察池页", () => {
  it("渲染列表", async () => {
    renderPage(<ObservationPage />);
    expect(screen.getByText("观察池管理")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("000001")).toBeInTheDocument();
    });
  });
});

describe("任务监控页", () => {
  it("渲染任务列表", async () => {
    renderPage(<JobsPage />);
    expect(screen.getByText("任务监控")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("refresh-data")).toBeInTheDocument();
    });
  });
});
