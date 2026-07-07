/**
 * T18: 策略组件测试（StrategyCard / StrategyTable）。
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StrategyCard } from "@/components/strategy/StrategyCard";
import { StrategyTable } from "@/components/strategy/StrategyTable";
import type { StrategySummary } from "@/types/api";

const base: StrategySummary = {
  strategy_id: "strat-1",
  prototype_id: "quality",
  domain: "价值",
  rank_in_domain: 1,
  composite_score: 88,
  annual_return: 0.18,
  sharpe: 1.4,
  max_drawdown: -0.1,
  adopted: false,
  disabled: false,
};

describe("StrategyCard", () => {
  it("渲染策略 ID 与指标", () => {
    render(<StrategyCard s={base} />);
    expect(screen.getByText("strat-1")).toBeInTheDocument();
    expect(screen.getByText("88.00")).toBeInTheDocument();
    expect(screen.getByText("18.00%")).toBeInTheDocument();
  });
  it("已采用显示徽标", () => {
    render(<StrategyCard s={{ ...base, adopted: true }} />);
    expect(screen.getByText("已采用")).toBeInTheDocument();
  });
  it("停用显示徽标", () => {
    render(<StrategyCard s={{ ...base, disabled: true }} />);
    expect(screen.getByText("已停用")).toBeInTheDocument();
  });
});

describe("StrategyTable", () => {
  it("空数据显示占位行", () => {
    render(<StrategyTable items={[]} />);
    expect(screen.getByText("暂无策略")).toBeInTheDocument();
  });
  it("多行渲染", () => {
    render(
      <StrategyTable
        items={[base, { ...base, strategy_id: "strat-2" }]}
      />,
    );
    expect(screen.getByText("strat-1")).toBeInTheDocument();
    expect(screen.getByText("strat-2")).toBeInTheDocument();
  });
});
