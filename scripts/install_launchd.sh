#!/usr/bin/env bash
# install_launchd.sh — 一键安装 launchd 定时任务（Feature #3 / T11）
#
# 用法：
#   bash scripts/install_launchd.sh           # 安装
#   bash scripts/install_launchd.sh uninstall # 卸载
#
# 详见 specs/003-scheduler/spec.md AC-5
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LABEL="com.trandeagent.daily"
PLIST_DIR="${HOME}/Library/LaunchAgents"
PLIST_PATH="${PLIST_DIR}/${LABEL}.plist"

mkdir -p "${PLIST_DIR}"
mkdir -p "${PROJECT_ROOT}/logs"

if [[ "${1:-install}" == "uninstall" ]]; then
    echo "→ 卸载 launchd agent：${LABEL}"
    if [[ -f "${PLIST_PATH}" ]]; then
        launchctl unload "${PLIST_PATH}" 2>/dev/null || true
        rm -f "${PLIST_PATH}"
        echo "✅ 已删除 plist：${PLIST_PATH}"
    else
        echo "ℹ️  plist 不存在，无需卸载"
    fi
    exit 0
fi

echo "→ 安装 launchd agent：${LABEL}"
# 通过 CLI 生成 plist 并加载（复用 LaunchdScheduler.install，保证字段一致）
cd "${PROJECT_ROOT}"
uv run python -m src.scheduler install

echo "→ 验证：launchctl list | grep ${LABEL}"
if launchctl list | grep -q "${LABEL}"; then
    echo "✅ 安装成功：launchctl 已加载 ${LABEL}"
else
    echo "⚠️  未在 launchctl list 中发现 ${LABEL}（可能加载延迟，稍后重试）"
    exit 1
fi
