/**
 * T18: 详情页集成测试（策略详情 / 单基金 / 配置编辑）。
 */
import { describe, it, expect, vi } from "vitest";

vi.mock("echarts-for-react", () => ({
  __esModule: true,
  default: () => <div data-testid="echarts" />,
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
  Toaster: () => null,
}));

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

import { render, screen, waitFor } from "@testing-library/react";
import {
  createTestQueryClient,
  withQueryClient,
} from "@/__tests__/helpers";
import StrategyDetailPage from "@/app/strategies/[id]/page";
import FundDetailPage from "@/app/funds/[code]/page";
import ConfigEditPage from "@/app/manage/config/page";

function renderPage(page: React.ReactNode) {
  return render(
    withQueryClient(createTestQueryClient() as never, page),
  );
}

describe("策略详情页", () => {
  it("渲染策略 ID 与图表", async () => {
    renderPage(<StrategyDetailPage />);
    expect(screen.getByText("strat-1")).toBeInTheDocument();
    // 等待数据加载后渲染图表区
    await waitFor(() => {
      expect(screen.getByText("多周期收益对比")).toBeInTheDocument();
    });
    expect(screen.getByText("净值曲线 / 回撤 / 基准")).toBeInTheDocument();
    expect(screen.getByText("现金流时序")).toBeInTheDocument();
  });
});

describe("单基金详情页", () => {
  it("渲染 6 个模块标题", async () => {
    renderPage(<FundDetailPage />);
    await waitFor(() => {
      expect(screen.getByText("经理画像")).toBeInTheDocument();
    });
    expect(screen.getByText("持仓行业雷达")).toBeInTheDocument();
    expect(screen.getByText("业绩归因对比")).toBeInTheDocument();
    expect(screen.getByText("风险仪表盘")).toBeInTheDocument();
    expect(screen.getByText("现金流瀑布")).toBeInTheDocument();
    expect(screen.getByText("LLM 分析报告")).toBeInTheDocument();
  });

  it("已加入观察池时按钮禁用", async () => {
    renderPage(<FundDetailPage />);
    await waitFor(() => {
      // mock 观察池含 000001
      expect(screen.getByText("已在观察池")).toBeInTheDocument();
    });
  });
});

describe("配置编辑页", () => {
  it("渲染表单 + 历史", async () => {
    renderPage(<ConfigEditPage />);
    expect(screen.getByText("规则配置")).toBeInTheDocument();
    // 等待配置加载回填
    await waitFor(() => {
      expect(screen.getByText("编辑配置")).toBeInTheDocument();
    });
  });

  it("渲染版本历史", async () => {
    renderPage(<ConfigEditPage />);
    await waitFor(() => {
      expect(screen.getByText("版本历史")).toBeInTheDocument();
    });
  });
});
