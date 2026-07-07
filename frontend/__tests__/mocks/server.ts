/**
 * T18: MSW 测试服务器（单例）。
 */
import { setupServer } from "msw/node";
import { handlers } from "./handlers";

export const server = setupServer(...handlers);
