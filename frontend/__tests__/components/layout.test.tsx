/**
 * T18: 布局组件测试（Sidebar / Topbar）。
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { Sidebar } from "@/components/layout/Sidebar";

// mock next/navigation & next/link
vi.mock("next/navigation", () => ({
  usePathname: () => "/strategies",
}));

vi.mock("next/link", () => ({
  __esModule: true,
  default: ({
    children,
    href,
    className,
  }: {
    children: React.ReactNode;
    href: string;
    className?: string;
  }) => (
    <a href={href} className={className} data-testid="nav-link">
      {children}
    </a>
  ),
}));

describe("Sidebar", () => {
  it("渲染 4 个导航项", () => {
    render(<Sidebar />);
    expect(screen.getByText("首页")).toBeInTheDocument();
    expect(screen.getByText("策略池")).toBeInTheDocument();
    expect(screen.getByText("发现")).toBeInTheDocument();
    expect(screen.getByText("管理台")).toBeInTheDocument();
  });
  it("当前路由 /strategies 高亮策略池", () => {
    render(<Sidebar />);
    const links = screen.getAllByTestId("nav-link");
    const poolLink = links.find((l) => l.getAttribute("href") === "/strategies");
    expect(poolLink?.className).toContain("text-primary");
  });
});
