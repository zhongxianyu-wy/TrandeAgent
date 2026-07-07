/**
 * T18: 页面交互测试（点击按钮触发 mutation，覆盖 handler 函数）。
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("echarts-for-react", () => ({
  __esModule: true,
  default: () => <div data-testid="echarts" />,
}));

// 用 vi.hoisted 让 mock 引用安全（vi.mock 会被提升到文件顶部）
const { toastMock } = vi.hoisted(() => ({
  toastMock: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}));
vi.mock("sonner", () => ({
  toast: toastMock,
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
import userEvent from "@testing-library/user-event";
import {
  createTestQueryClient,
  withQueryClient,
} from "@/__tests__/helpers";
import StrategyDetailPage from "@/app/strategies/[id]/page";
import FundDetailPage from "@/app/funds/[code]/page";
import ObservationPage from "@/app/manage/observation/page";
import JobsPage from "@/app/manage/jobs/page";
import ManagePage from "@/app/manage/page";
import ConfigEditPage from "@/app/manage/config/page";

function renderPage(page: React.ReactNode) {
  return render(
    withQueryClient(createTestQueryClient() as never, page),
  );
}

beforeEach(() => {
  toastMock.success.mockClear();
  toastMock.error.mockClear();
  toastMock.info.mockClear();
});

describe("策略详情 - 采用策略", () => {
  it("点击采用按钮触发 toast", async () => {
    const user = userEvent.setup();
    renderPage(<StrategyDetailPage />);
    await waitFor(() => {
      expect(screen.getByText("采用策略")).toBeInTheDocument();
    });
    await user.click(screen.getByText("采用策略"));
    await waitFor(() => {
      expect(toastMock.success).toHaveBeenCalled();
    });
  });
});

describe("单基金 - 加入观察池与重新分析", () => {
  it("触发 AI 重新分析按钮", async () => {
    const user = userEvent.setup();
    renderPage(<FundDetailPage />);
    await waitFor(() => {
      expect(screen.getByText("LLM 分析报告")).toBeInTheDocument();
    });
    const btn = screen.getByText("触发 AI 重新分析");
    await user.click(btn);
    await waitFor(() => {
      expect(toastMock.success).toHaveBeenCalledWith(
        expect.stringContaining("已触发 AI 重新分析"),
      );
    });
  });
});

describe("观察池 - 加入/移出", () => {
  it("输入代码加入观察池", async () => {
    const user = userEvent.setup();
    renderPage(<ObservationPage />);
    await waitFor(() => {
      expect(screen.getByPlaceholderText("如 000001")).toBeInTheDocument();
    });
    await user.type(screen.getByPlaceholderText("如 000001"), "000099");
    await user.click(screen.getByText("加入"));
    await waitFor(() => {
      expect(toastMock.success).toHaveBeenCalledWith("已加入观察池");
    });
  });

  it("移出观察池", async () => {
    const user = userEvent.setup();
    const { within } = await import("@testing-library/react");
    renderPage(<ObservationPage />);
    await waitFor(() => {
      expect(screen.getAllByText("移出").length).toBeGreaterThan(0);
    });
    const removeBtns = screen.getAllByText("移出");
    await user.click(removeBtns[0]);
    // 弹出确认框后，点击对话框内的"移出"确认按钮
    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });
    const dialog = screen.getByRole("dialog");
    await user.click(within(dialog).getByText("移出"));
    await waitFor(() => {
      expect(toastMock.success).toHaveBeenCalledWith("已移出观察池");
    });
  });
});

describe("任务监控 - 触发任务", () => {
  it("点击数据刷新按钮", async () => {
    const user = userEvent.setup();
    renderPage(<JobsPage />);
    await waitFor(() => {
      expect(screen.getByText("数据刷新")).toBeInTheDocument();
    });
    await user.click(screen.getByText("数据刷新"));
    await waitFor(() => {
      expect(toastMock.success).toHaveBeenCalledWith(
        expect.stringContaining("数据刷新"),
      );
    });
  });

  it("点击回测按钮", async () => {
    const user = userEvent.setup();
    renderPage(<JobsPage />);
    await waitFor(() => {
      expect(screen.getByText("回测")).toBeInTheDocument();
    });
    await user.click(screen.getByText("回测"));
    await waitFor(() => {
      expect(toastMock.success).toHaveBeenCalledWith(
        expect.stringContaining("回测"),
      );
    });
  });

  it("切换状态筛选", async () => {
    const user = userEvent.setup();
    renderPage(<JobsPage />);
    await waitFor(() => {
      expect(screen.getByText("成功")).toBeInTheDocument();
    });
    await user.click(screen.getByText("成功"));
    // 切换后重新请求（不报错即可）
    expect(screen.getByText("任务列表")).toBeInTheDocument();
  });
});

describe("管理台首页 - 触发数据刷新", () => {
  it("点击触发数据刷新", async () => {
    const user = userEvent.setup();
    renderPage(<ManagePage />);
    await waitFor(() => {
      expect(screen.getByText("触发数据刷新")).toBeInTheDocument();
    });
    await user.click(screen.getByText("触发数据刷新"));
    await waitFor(() => {
      expect(toastMock.success).toHaveBeenCalled();
    });
  });
});

describe("配置编辑 - 保存", () => {
  it("提交表单并确认保存", async () => {
    const user = userEvent.setup();
    renderPage(<ConfigEditPage />);
    await waitFor(() => {
      expect(screen.getByText("保存并预览影响")).toBeInTheDocument();
    });
    // 点击保存 → 弹出确认框
    await user.click(screen.getByText("保存并预览影响"));
    await waitFor(() => {
      expect(screen.getByText("确认保存")).toBeInTheDocument();
    });
    // 确认
    await user.click(screen.getByText("确认保存"));
    await waitFor(() => {
      expect(toastMock.success).toHaveBeenCalledWith(
        expect.stringContaining("已保存"),
      );
    });
  });

  it("点击回滚按钮弹出确认框并回滚", async () => {
    const user = userEvent.setup();
    renderPage(<ConfigEditPage />);
    // 等待版本历史加载
    await waitFor(() => {
      expect(screen.getByText("回滚")).toBeInTheDocument();
    });
    // 点击回滚 → 弹出确认框
    await user.click(screen.getAllByText("回滚")[0]);
    await waitFor(() => {
      expect(screen.getByText("确认回滚")).toBeInTheDocument();
    });
    // 确认回滚
    await user.click(screen.getByText("确认回滚"));
    await waitFor(() => {
      expect(toastMock.success).toHaveBeenCalledWith(
        expect.stringContaining("已回滚"),
      );
    });
  });
});

describe("策略详情 - 重新生成策略", () => {
  it("点击重新生成按钮提交任务", async () => {
    const user = userEvent.setup();
    renderPage(<StrategyDetailPage />);
    await waitFor(() => {
      expect(screen.getByText("重新生成策略")).toBeInTheDocument();
    });
    await user.click(screen.getByText("重新生成策略"));
    await waitFor(() => {
      expect(toastMock.success).toHaveBeenCalledWith(
        expect.stringContaining("已提交重新生成任务"),
      );
    });
  });
});
