/**
 * T18: 通用组件测试（ErrorBoundary / LoadingSkeleton / ConfirmModal）。
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  CardSkeleton,
  RowSkeleton,
  TableSkeleton,
  ListSkeleton,
  ChartSkeleton,
  PageSkeleton,
} from "@/components/common/LoadingSkeleton";
import { ErrorBoundary } from "@/components/common/ErrorBoundary";
import { ConfirmModal } from "@/components/common/ConfirmModal";

describe("LoadingSkeleton", () => {
  it("CardSkeleton 渲染", () => {
    const { container } = render(<CardSkeleton />);
    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(
      0,
    );
  });
  it("RowSkeleton 含 N 个骨架", () => {
    const { container } = render(<RowSkeleton cols={4} />);
    expect(container.querySelectorAll(".animate-pulse")).toHaveLength(4);
  });
  it("TableSkeleton 多行", () => {
    const { container } = render(<TableSkeleton rows={3} cols={3} />);
    expect(container.querySelectorAll(".animate-pulse").length).toBe(9);
  });
  it("ListSkeleton", () => {
    render(<ListSkeleton items={2} />);
    // 无强断言，仅确认渲染不报错
    expect(document.body).toBeTruthy();
  });
  it("ChartSkeleton", () => {
    const { container } = render(<ChartSkeleton />);
    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(
      0,
    );
  });
  it("PageSkeleton", () => {
    render(<PageSkeleton />);
    expect(document.body).toBeTruthy();
  });
});

describe("ErrorBoundary", () => {
  it("正常子组件直通渲染", () => {
    render(
      <ErrorBoundary>
        <div>hello</div>
      </ErrorBoundary>,
    );
    expect(screen.getByText("hello")).toBeInTheDocument();
  });

  it("捕获错误并展示兜底", () => {
    // 屏蔽 console.error 噪音
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    const flag = true;
    function Boom(): React.ReactNode {
      if (flag) throw new Error("boom!");
      return null;
    }
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );
    expect(screen.getByText("页面出错了")).toBeInTheDocument();
    expect(screen.getByText(/boom!/)).toBeInTheDocument();
    spy.mockRestore();
  });

  it("重试按钮重置错误", async () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    let shouldThrow = true;
    function Maybe() {
      if (shouldThrow) throw new Error("x");
      return <div>recovered</div>;
    }
    const user = userEvent.setup();
    render(
      <ErrorBoundary>
        <Maybe />
      </ErrorBoundary>,
    );
    shouldThrow = false;
    await user.click(screen.getByText("重试"));
    expect(screen.getByText("recovered")).toBeInTheDocument();
    spy.mockRestore();
  });
});

describe("ConfirmModal", () => {
  it("open=false 不渲染", () => {
    render(
      <ConfirmModal
        open={false}
        onOpenChange={() => {}}
        onConfirm={() => {}}
      />,
    );
    expect(screen.queryByText("确认操作")).not.toBeInTheDocument();
  });

  it("确认触发 onConfirm", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    const onOpenChange = vi.fn();
    render(
      <ConfirmModal
        open
        onOpenChange={onOpenChange}
        onConfirm={onConfirm}
        title="删除"
        confirmText="删掉"
      />,
    );
    expect(screen.getByText("删除")).toBeInTheDocument();
    await user.click(screen.getByText("删掉"));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });
});
