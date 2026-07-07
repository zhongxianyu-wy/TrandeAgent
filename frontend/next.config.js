/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // 后端通过环境变量配置，默认 http://localhost:8000
  env: {
    NEXT_PUBLIC_API_BASE:
      process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000",
  },
};

module.exports = nextConfig;
