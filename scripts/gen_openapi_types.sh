#!/usr/bin/env bash
# OpenAPI 类型生成脚本（T13 / AC-4）
#
# 用途：从后端 FastAPI 应用的 OpenAPI schema 生成前端 TypeScript 类型，
#       供 Next.js 前端直接 import 使用。
#
# 用法：
#   1. 启动后端：uv run python -m src.api
#   2. 运行：  bash scripts/gen_openapi_types.sh
#
# 也可直接读取本地导出的 openapi.json（无需启动服务）：
#   bash scripts/gen_openapi_types.sh --local
#
# 依赖：openapi-typescript（npm i -g openapi-typescript 或 npx）。
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT="${1:-${ROOT_DIR}/frontend/types/api.ts}"
SOURCE="${2:-http://localhost:8000/openapi.json}"

echo "==> 生成 OpenAPI TypeScript 类型"
echo "    源: ${SOURCE}"
echo "    目标: ${OUTPUT}"

mkdir -p "$(dirname "${OUTPUT}")"

if [ "${1:-}" = "--local" ]; then
  # 直接从 app 导出 openapi.json，再转 TS（无需启动服务）
  echo "==> 本地模式：导出 openapi.json"
  cd "${ROOT_DIR}"
  uv run python -c "import json; from src.api.app import app; print(json.dumps(app.openapi()))" \
    > "${ROOT_DIR}/openapi.json"
  SOURCE="${ROOT_DIR}/openapi.json"
fi

if command -v openapi-typescript >/dev/null 2>&1; then
  openapi-typescript "${SOURCE}" -o "${OUTPUT}"
elif command -v npx >/dev/null 2>&1; then
  npx --yes openapi-typescript "${SOURCE}" -o "${OUTPUT}"
else
  echo "错误：未找到 openapi-typescript，请先执行 npm i -g openapi-typescript" >&2
  exit 1
fi

echo "==> 完成：${OUTPUT}"
