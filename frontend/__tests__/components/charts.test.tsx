/**
 * T18: 图表组件渲染测试。
 * ECharts 在 jsdom 中不真实渲染 canvas，仅验证 option 处理逻辑（空态兜底）。
 */
import { describe, it, expect, vi } from "vitest";

// mock echarts-for-react，避免 jsdom canvas 报错（必须在 import 组件前）
vi.mock("echarts-for-react", () => ({
  __esModule: true,
  default: () => <div data-testid="echarts" />,
}));

import { render, screen } from "@testing-library/react";
import { PeriodReturnChart } from "@/components/charts/PeriodReturnChart";
import { NavCurveChart } from "@/components/charts/NavCurveChart";
import { CashflowChart } from "@/components/charts/CashflowChart";

describe("PeriodReturnChart", () => {
  it("空数据显示占位", () => {
    render(<PeriodReturnChart data={null} />);
    expect(screen.getByText("暂无周期数据")).toBeInTheDocument();
  });
  it("有数据渲染 echarts", () => {
    render(
      <PeriodReturnChart
        data={{
          period: "monthly",
          labels: ["1月", "2月"],
          returns: [0.1, -0.05],
          benchmark_returns: [0.05, 0.0],
        }}
      />,
    );
    expect(screen.getByTestId("echarts")).toBeInTheDocument();
  });
});

describe("NavCurveChart", () => {
  it("空数据显示占位", () => {
    render(<NavCurveChart data={null} />);
    expect(screen.getByText("暂无净值数据")).toBeInTheDocument();
  });
  it("有数据渲染", () => {
    render(
      <NavCurveChart
        data={{
          dates: ["2026-01", "2026-02"],
          nav: [1, 1.1],
          drawdown: [0, -0.05],
          benchmark_nav: [1, 1.05],
        }}
      />,
    );
    expect(screen.getByTestId("echarts")).toBeInTheDocument();
  });
});

describe("CashflowChart", () => {
  it("空数据显示占位", () => {
    render(<CashflowChart data={null} />);
    expect(screen.getByText("暂无现金流数据")).toBeInTheDocument();
  });
  it("有数据渲染", () => {
    render(
      <CashflowChart
        data={{
          dates: ["Q1", "Q2"],
          share_change: [100, -50],
          institution_holding: [10, 12],
        }}
      />,
    );
    expect(screen.getByTestId("echarts")).toBeInTheDocument();
  });
});
