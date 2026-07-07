/**
 * T18: 单基金页模块测试。
 */
import { describe, it, expect, vi } from "vitest";

// mock echarts-for-react
vi.mock("echarts-for-react", () => ({
  __esModule: true,
  default: () => <div data-testid="echarts" />,
}));

import { render, screen } from "@testing-library/react";
import { ManagerProfileCard } from "@/components/fund/ManagerProfile";
import { HoldingsRadar } from "@/components/fund/HoldingsRadar";
import { PerformanceAttributionTable } from "@/components/fund/PerformanceAttribution";
import { RiskGaugeCard } from "@/components/fund/RiskGauge";
import { CashflowWaterfall } from "@/components/fund/CashflowWaterfall";
import { LlmReportCard } from "@/components/fund/LlmReport";
import type {
  Holdings,
  PerformanceAttribution,
  FundIndicators,
  Cashflow,
  LlmReport,
} from "@/types/api";

describe("ManagerProfileCard", () => {
  it("无数据显示占位", () => {
    render(<ManagerProfileCard holdings={null} />);
    expect(screen.getByText("暂无经理历史数据")).toBeInTheDocument();
  });
  it("渲染时间轴", () => {
    const h: Holdings = {
      fund_code: "000001",
      manager_profile: {
        name: "张三",
        tenure_years: 5,
        history: [
          { period: "2018-2024", fund: "测试", scale: 1e8, return: 0.2 },
        ],
      },
    };
    render(<ManagerProfileCard holdings={h} />);
    expect(screen.getByText(/张三/)).toBeInTheDocument();
    expect(screen.getByText("测试")).toBeInTheDocument();
  });
});

describe("HoldingsRadar", () => {
  it("无数据占位", () => {
    render(<HoldingsRadar holdings={null} />);
    expect(screen.getByText("暂无持仓行业数据")).toBeInTheDocument();
  });
  it("有数据渲染 echarts", () => {
    render(
      <HoldingsRadar
        holdings={{
          fund_code: "000001",
          industries: [
            { industry: "科技", weight: 0.3 },
            { industry: "消费", weight: 0.2 },
          ],
        }}
      />,
    );
    expect(screen.getByTestId("echarts")).toBeInTheDocument();
  });
});

describe("PerformanceAttributionTable", () => {
  it("无数据占位", () => {
    render(<PerformanceAttributionTable data={null} />);
    expect(screen.getByText("暂无归因数据")).toBeInTheDocument();
  });
  it("3 列对比渲染", () => {
    const d: PerformanceAttribution = {
      metrics: ["收益", "夏普"],
      fund: [0.2, 1.5],
      peer_avg: [0.1, 1.0],
      hs300: [0.05, 0.8],
    };
    render(<PerformanceAttributionTable data={d} />);
    expect(screen.getByText("收益")).toBeInTheDocument();
    expect(screen.getAllByText("20.00%").length).toBeGreaterThan(0);
  });
});

describe("RiskGaugeCard", () => {
  it("渲染仪表盘 + 指标", () => {
    const ind: FundIndicators = {
      l2_performance: { sharpe: 1.5, max_drawdown: -0.2, volatility: 0.18 },
    };
    render(<RiskGaugeCard indicators={ind} />);
    expect(screen.getByText("最大回撤")).toBeInTheDocument();
    expect(screen.getByText("-20.00%")).toBeInTheDocument();
  });
});

describe("CashflowWaterfall", () => {
  it("无数据占位", () => {
    render(<CashflowWaterfall data={null} />);
    expect(screen.getByText("暂无现金流数据")).toBeInTheDocument();
  });
  it("有数据渲染", () => {
    const d: Cashflow = {
      fund_code: "000001",
      dates: ["Q1", "Q2"],
      share_change: [100, -50],
    };
    render(<CashflowWaterfall data={d} />);
    expect(screen.getByTestId("echarts")).toBeInTheDocument();
  });
});

describe("LlmReportCard", () => {
  it("无数据占位", () => {
    render(<LlmReportCard data={null} />);
    expect(
      screen.getByText(/暂无报告，可点击右上角/),
    ).toBeInTheDocument();
  });
  it("渲染 markdown + 依据按钮", () => {
    const d: LlmReport = {
      fund_code: "000001",
      markdown: "## 标题\n该基金表现 **优秀**，依据【夏普高】",
      references: [{ label: "夏普高" }],
    };
    render(<LlmReportCard data={d} />);
    expect(screen.getByText("标题")).toBeInTheDocument();
    expect(screen.getByText("优秀")).toBeInTheDocument();
    expect(screen.getByText("夏普高")).toBeInTheDocument();
  });
  it("JSON 原文可展开", async () => {
    const user = (await import("@testing-library/user-event")).default;
    const d: LlmReport = {
      fund_code: "000001",
      markdown: "正文",
      json: { score: 90 },
    };
    render(<LlmReportCard data={d} />);
    expect(screen.queryByText('"score"')).not.toBeInTheDocument();
    await user.click(screen.getByText("JSON 原文"));
    expect(screen.getByText(/"score"/)).toBeInTheDocument();
  });
});
