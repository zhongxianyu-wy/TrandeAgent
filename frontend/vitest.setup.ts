/**
 * vitest 测试环境初始化：jsdom + jest-dom matchers + msw server。
 */
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeAll, afterAll } from "vitest";
import { server } from "@/__tests__/mocks/server";

// React Query 全局默认（测试用）
process.env.NEXT_PUBLIC_API_BASE = "http://localhost:8000";

// MSW：拦截所有 fetch，由 handler 决定响应
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
});
afterAll(() => server.close());
