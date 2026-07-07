"""调度层 CLI（plan §7 / T10）。

用法：
    python -m src.scheduler install              # 安装 launchd agent
    python -m src.scheduler uninstall            # 卸载
    python -m src.scheduler status               # 查看安装与最近运行状态
    python -m src.scheduler run [--force] [--dry-run]

`run` 流程（spec FR-3 / FR-4）：
1. 非交易日且非 --force → 直接退出
2. 检测漏推送 → backfill
3. 执行当日流水线 → record_run
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date

from loguru import logger

from src.scheduler.config import load_scheduler_config
from src.scheduler.launchd_scheduler import LaunchdScheduler


def _cmd_install(scheduler: LaunchdScheduler) -> int:
    scheduler.install()
    print(f"✅ 已安装 launchd agent：{scheduler.config.label}")
    print(f"   plist: {scheduler.config.launchd_plist_path}")
    print(f"   触发时间: {scheduler.config.trigger_time} ({scheduler.config.timezone})")
    print("   验证: launchctl list | grep trandeagent")
    return 0


def _cmd_uninstall(scheduler: LaunchdScheduler) -> int:
    scheduler.uninstall()
    print(f"✅ 已卸载 launchd agent：{scheduler.config.label}")
    return 0


def _cmd_status(scheduler: LaunchdScheduler) -> int:
    installed = scheduler.is_installed()
    print("=" * 50)
    print("调度层状态")
    print("=" * 50)
    print(f"launchd agent: {'✅ 已安装' if installed else '❌ 未安装'}")
    print(f"Label:         {scheduler.config.label}")
    print(f"触发时间:       {scheduler.config.trigger_time} ({scheduler.config.timezone})")
    print(f"补发上限:       {scheduler.config.backfill_max_days} 个交易日")
    print()
    last = scheduler.state.load_last_run()
    if last:
        print("最近一次运行:")
        print(f"  日期: {last.get('last_run_date')}")
        print(f"  时间: {last.get('last_run_at')}")
        print(f"  状态: {last.get('last_status')}")
        print(f"  耗时: {last.get('last_duration_sec')} 秒")
    else:
        print("最近一次运行: （无记录）")
    print()
    missed = scheduler.detect_missed_runs()
    if missed:
        print(f"⚠️  检测到 {len(missed)} 个漏推送交易日：{missed}")
    else:
        print("✅ 无漏推送")
    return 0


def _cmd_run(scheduler: LaunchdScheduler, force: bool, dry_run: bool) -> int:
    """执行一次运行（spec FR-3 / FR-4）。"""
    today = scheduler.today
    mode = "dry_run" if dry_run else ("force" if force else "daily")

    # 1. 交易日过滤（spec FR-2）
    if not force and not dry_run:
        if not scheduler.should_run_today(today):
            logger.info("{} 非交易日，跳过（使用 --force 强制运行）", today)
            print(f"{today} 非交易日，跳过")
            return 0

    # 2. 漏推送补发（spec FR-3）
    missed = scheduler.detect_missed_runs()
    if missed:
        logger.info("检测到 {} 个漏推送交易日，开始补发：{}", len(missed), missed)
        if not dry_run:
            scheduler.backfill(missed)
        else:
            print(f"[dry-run] 将补发 {len(missed)} 个交易日：{missed}")

    # 3. 执行当日流水线（spec FR-1）
    logger.info("开始执行 {} 流水线：{}", mode, today)
    start = time.time()
    if dry_run:
        print(f"[dry-run] 模拟运行 {today}（mode={mode}），不写状态")
        return 0

    try:
        status, duration_sec, fund_count = scheduler.runner(today, mode)
    except Exception as e:
        duration_sec = int(time.time() - start)
        logger.error("运行异常：{}", e)
        scheduler.record_run("failed", duration_sec, mode)
        return 1

    if duration_sec <= 0:
        duration_sec = int(time.time() - start)
    scheduler.record_run(status, duration_sec, mode)
    print(
        f"✅ 运行完成：{today} status={status} "
        f"duration={duration_sec}s fund_count={fund_count} mode={mode}"
    )
    return 0 if status != "failed" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="src.scheduler", description="调度层 CLI（Feature #3）"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("install", help="安装 launchd agent")
    sub.add_parser("uninstall", help="卸载 launchd agent")
    sub.add_parser("status", help="查看安装与最近运行状态")

    p_run = sub.add_parser("run", help="执行一次运行")
    p_run.add_argument(
        "--force", action="store_true", help="强制运行（忽略交易日过滤）"
    )
    p_run.add_argument(
        "--dry-run", action="store_true", help="模拟运行，不推送不写状态"
    )
    p_run.add_argument("--config", help="指定 scheduler.yaml 路径")

    args = parser.parse_args(argv)

    config = load_scheduler_config(getattr(args, "config", None))
    scheduler = LaunchdScheduler(config)

    if args.command == "install":
        return _cmd_install(scheduler)
    if args.command == "uninstall":
        return _cmd_uninstall(scheduler)
    if args.command == "status":
        return _cmd_status(scheduler)
    if args.command == "run":
        return _cmd_run(scheduler, args.force, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
