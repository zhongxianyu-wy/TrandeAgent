#!/usr/bin/env bash
# scripts/serve.sh — 一键启停本机部署（macOS）
#
# 用法：
#   bash scripts/serve.sh start     # 启动后端(8000) + 前端(3000)
#   bash scripts/serve.sh stop      # 停止所有服务
#   bash scripts/serve.sh restart   # 重启
#   bash scripts/serve.sh status    # 查看运行状态
#
# 架构：
#   后端：uv run uvicorn ... :8000（FastAPI）
#   前端：npm run start :3000（Next.js 生产模式）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKEND_PID_FILE="${PROJECT_ROOT}/logs/backend.pid"
FRONTEND_PID_FILE="${PROJECT_ROOT}/logs/frontend.pid"
BACKEND_LOG="${PROJECT_ROOT}/logs/backend.log"
FRONTEND_LOG="${PROJECT_ROOT}/logs/frontend.log"

mkdir -p "${PROJECT_ROOT}/logs"

BACKEND_PORT=8000
FRONTEND_PORT=3000

is_running() {
    local pid_file="$1"
    [[ -f "$pid_file" ]] || return 1
    local pid
    pid=$(cat "$pid_file")
    [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

start_backend() {
    if is_running "$BACKEND_PID_FILE"; then
        echo "后端已在运行（PID $(cat "$BACKEND_PID_FILE")）"
        return 0
    fi
    echo "→ 启动后端（uvicorn :${BACKEND_PORT}）..."
    cd "$PROJECT_ROOT"
    nohup uv run uvicorn src.api.app:app \
        --host 127.0.0.1 --port ${BACKEND_PORT} \
        --log-level info > "$BACKEND_LOG" 2>&1 &
    echo $! > "$BACKEND_PID_FILE"
    sleep 2
    if is_running "$BACKEND_PID_FILE"; then
        echo "  后端已启动（PID $(cat "$BACKEND_PID_FILE")），日志：${BACKEND_LOG}"
    else
        echo "  ❌ 后端启动失败，查看日志：tail -50 ${BACKEND_LOG}"
        exit 1
    fi
}

start_frontend() {
    if is_running "$FRONTEND_PID_FILE"; then
        echo "前端已在运行（PID $(cat "$FRONTEND_PID_FILE")）"
        return 0
    fi
    echo "→ 启动前端（next start :${FRONTEND_PORT}）..."
    cd "${PROJECT_ROOT}/frontend"
    # 确保已构建
    if [[ ! -d ".next" ]]; then
        echo "  .next 不存在，先执行 npm run build..."
        npm run build > "$FRONTEND_LOG" 2>&1
    fi
    nohup npm run start -- -p ${FRONTEND_PORT} > "$FRONTEND_LOG" 2>&1 &
    echo $! > "$FRONTEND_PID_FILE"
    sleep 3
    if is_running "$FRONTEND_PID_FILE"; then
        echo "  前端已启动（PID $(cat "$FRONTEND_PID_FILE")），日志：${FRONTEND_LOG}"
    else
        echo "  ❌ 前端启动失败，查看日志：tail -50 ${FRONTEND_LOG}"
        exit 1
    fi
}

stop_service() {
    local name="$1" pid_file="$2"
    if is_running "$pid_file"; then
        local pid
        pid=$(cat "$pid_file")
        echo "→ 停止${name}（PID ${pid}）..."
        kill "$pid" 2>/dev/null || true
        sleep 1
        kill -9 "$pid" 2>/dev/null || true
        rm -f "$pid_file"
        echo "  ${name}已停止"
    else
        echo "${name}未运行"
        rm -f "$pid_file"
    fi
}

show_status() {
    if is_running "$BACKEND_PID_FILE"; then
        echo "后端：运行中（PID $(cat "$BACKEND_PID_FILE")）: http://localhost:${BACKEND_PORT}"
    else
        echo "后端：未运行"
    fi
    if is_running "$FRONTEND_PID_FILE"; then
        echo "前端：运行中（PID $(cat "$FRONTEND_PID_FILE")）: http://localhost:${FRONTEND_PORT}"
    else
        echo "前端：未运行"
    fi
}

case "${1:-}" in
    start)
        start_backend
        start_frontend
        echo ""
        echo "✅ 服务已启动："
        echo "   前端：http://localhost:${FRONTEND_PORT}"
        echo "   后端：http://localhost:${BACKEND_PORT}/docs"
        ;;
    stop)
        stop_service "前端" "$FRONTEND_PID_FILE"
        stop_service "后端" "$BACKEND_PID_FILE"
        echo "✅ 所有服务已停止"
        ;;
    restart)
        "$0" stop
        sleep 1
        "$0" start
        ;;
    status)
        show_status
        ;;
    *)
        echo "用法：bash scripts/serve.sh {start|stop|restart|status}"
        exit 1
        ;;
esac
