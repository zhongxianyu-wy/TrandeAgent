"""LaunchdScheduler：macOS launchd 实现（plan §3 / T04-T09）。

职责：
- should_run_today：交易日过滤（holiday.py）
- detect_missed_runs：读 last_run，计算漏掉的交易日，截断到 backfill_max_days
- backfill：对指定日期补发（调 runner 回调），超上限截断
- record_run：写 last_run + run_history
- install/uninstall/is_installed：launchd plist 生命周期管理

runner 回调由下游 main.py 注入（当前 feature 不含 main.py，故默认 no-op+log），
保持调度层与业务解耦、可单测。
"""
from __future__ import annotations

import subprocess
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

from loguru import logger

from src.scheduler.config import SchedulerConfig
from src.scheduler.holiday import is_trading_day, trading_days_between
from src.scheduler.scheduler import Scheduler
from src.scheduler.state import StateStore

# 业务流水线回调签名：(运行日期, 模式) → (状态, 耗时秒, 基金数)
# mode ∈ {"daily", "force", "backfill", "dry_run"}；返回 status ∈ {"success","failed","partial"}
RunnerFn = Callable[[date, str], tuple[str, int, int]]


def _default_runner(d: date, mode: str) -> tuple[str, int, int]:
    """默认 runner：业务流水线尚未接入时占位（plan §4 下游=main.py）。

    记录 warning 后返回 success 占位，避免调度层阻塞。
    """
    logger.warning(
        "默认 runner 被调用（业务流水线未注入）：date={} mode={}", d, mode
    )
    return ("success", 0, 0)


class LaunchdScheduler(Scheduler):
    """macOS launchd 调度实现。"""

    def __init__(
        self,
        config: SchedulerConfig,
        *,
        state_dir: Path | None = None,
        today: date | None = None,
        runner: RunnerFn | None = None,
    ) -> None:
        self.config = config
        self.runner: RunnerFn = runner or _default_runner
        # 允许注入 state_dir（测试）与 today（测试）
        sdir = state_dir or config.state_path
        self.state = StateStore(
            last_run_file=sdir / "last_run.json",
            run_history_file=sdir / "run_history.jsonl",
        )
        self._today_override = today

    # ---- 内部 ----

    @property
    def today(self) -> date:
        """当前日期（可被测试覆写）。"""
        return self._today_override if self._today_override is not None else date.today()

    # ---- T02 交易日过滤 ----

    def should_run_today(self, today: date | None = None) -> bool:
        """判定是否为 A 股交易日（spec FR-2 / AC-2）。"""
        d = today if today is not None else self.today
        return is_trading_day(d)

    # ---- T04 漏推送检测 ----

    def detect_missed_runs(self) -> list[date]:
        """检测漏推送的交易日列表（spec FR-3 / AC-3）。

        读 last_run.json 的 last_run_date，计算 (last_run_date, today) 开区间内
        的交易日，截断到最近 backfill_max_days 个。
        无历史记录时返回空列表（首次运行不补发）。
        """
        last = self.state.load_last_run()
        if not last or not last.get("last_run_date"):
            logger.info("无 last_run 记录，跳过漏推送检测")
            return []
        try:
            last_date = date.fromisoformat(last["last_run_date"])
        except (ValueError, KeyError):
            logger.warning("last_run_date 解析失败：{!r}", last.get("last_run_date"))
            return []

        today = self.today
        if last_date >= today:
            # 时钟回拨或同日多次运行：无漏推送
            return []

        missed = trading_days_between(last_date, today)
        max_days = self.config.backfill_max_days
        if len(missed) > max_days:
            logger.warning(
                "漏推送 {} 个交易日，超过上限 {}，仅补最近 {} 个",
                len(missed), max_days, max_days,
            )
            missed = missed[-max_days:]
        return missed

    # ---- T05 补发（含 5 天上限） ----

    def backfill(self, dates: list[date]) -> None:
        """补发指定日期的报告（spec FR-3 / plan §6）。

        - 超过 backfill_max_days 的部分截断到最近 N 天（plan §6 决策）
        - 逐日调 runner(d, "backfill") 执行业务流水线
        - 每日结果写入 run_history（record_run 语义）
        """
        if not dates:
            return
        max_days = self.config.backfill_max_days
        if len(dates) > max_days:
            logger.warning(
                "补发请求 {} 天，超过上限 {}，仅补最近 {} 天",
                len(dates), max_days, max_days,
            )
            dates = list(dates)[-max_days:]

        logger.info("开始补发 {} 个交易日：{}", len(dates), dates)
        for d in dates:
            try:
                status, duration_sec, fund_count = self.runner(d, "backfill")
            except Exception as e:
                logger.error("补发 {} 异常：{}", d, e)
                self.state.record(
                    "failed", 0, "backfill",
                    run_date=d, error=str(e),
                )
                continue
            self.state.record(
                status, duration_sec, "backfill",
                run_date=d, fund_count=fund_count,
            )
        logger.info("补发完成：{} 个交易日", len(dates))

    # ---- T06 记录运行 ----

    def record_run(self, status: str, duration_sec: int, mode: str) -> None:
        """记录本次运行到历史（spec FR-5）。"""
        self.state.record(status, duration_sec, mode)

    # ---- T07 launchd plist 模板 ----

    def render_plist(self) -> str:
        """渲染 launchd plist XML（plan §3 模板）。

        字段来自 SchedulerConfig（触发时间 / 路径 / Label）。
        """
        cfg = self.config
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
            '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
            '<plist version="1.0">\n'
            '<dict>\n'
            f'    <key>Label</key>\n'
            f'    <string>{cfg.label}</string>\n'
            f'    <key>ProgramArguments</key>\n'
            '    <array>\n'
            '        <string>/usr/bin/env</string>\n'
            f'        <string>PATH={cfg.env_path}</string>\n'
            '        <string>python</string>\n'
            '        <string>-m</string>\n'
            f'        <string>{cfg.program_module}</string>\n'
            f'        <string>{cfg.program_command}</string>\n'
            '    </array>\n'
            '    <key>StartCalendarInterval</key>\n'
            '    <dict>\n'
            f'        <key>Hour</key><integer>{cfg.hour}</integer>\n'
            f'        <key>Minute</key><integer>{cfg.minute}</integer>\n'
            '    </dict>\n'
            f'    <key>StandardOutPath</key><string>{cfg.stdout_log}</string>\n'
            f'    <key>StandardErrorPath</key><string>{cfg.stderr_log}</string>\n'
            f'    <key>WorkingDirectory</key><string>{cfg.working_dir}</string>\n'
            '</dict>\n'
            '</plist>\n'
        )

    # ---- T08 install/uninstall ----

    def install(self) -> None:
        """安装 launchd agent（spec FR-1 / AC-5）。

        - 渲染并写入 ~/Library/LaunchAgents/{label}.plist
        - `launchctl load` 加载
        - 确保日志目录存在
        """
        cfg = self.config
        # 确保日志目录存在
        cfg.stdout_log.parent.mkdir(parents=True, exist_ok=True)

        plist_path = cfg.launchd_plist_path
        plist_path.parent.mkdir(parents=True, exist_ok=True)

        # 已安装先卸载，保证幂等
        if self.is_installed():
            logger.info("检测到已安装，先卸载再重装")
            self._unload()

        plist_path.write_text(self.render_plist(), encoding="utf-8")
        logger.info("plist 已写入：{}", plist_path)
        self._load()
        logger.info("launchd agent 已加载：{}", cfg.label)

    def uninstall(self) -> None:
        """卸载 launchd agent（AC-5）。"""
        cfg = self.config
        plist_path = cfg.launchd_plist_path
        if plist_path.is_file():
            self._unload()
            plist_path.unlink()
            logger.info("已删除 plist：{}", plist_path)
        else:
            logger.info("plist 不存在，无需卸载：{}", plist_path)

    def _load(self) -> None:
        """launchctl load。"""
        subprocess.run(
            ["launchctl", "load", str(self.config.launchd_plist_path)],
            check=True,
            capture_output=True,
        )

    def _unload(self) -> None:
        """launchctl unload（忽略未加载错误）。"""
        result = subprocess.run(
            ["launchctl", "unload", str(self.config.launchd_plist_path)],
            capture_output=True,
        )
        if result.returncode != 0:
            logger.debug(
                "launchctl unload 返回非零（可能未加载）：{}",
                result.stderr.decode("utf-8", errors="replace").strip(),
            )

    # ---- T09 is_installed ----

    def is_installed(self) -> bool:
        """判定 launchd agent 是否已安装（AC-5）。

        满足以下任一即视为已安装：
        - plist 文件存在于 ~/Library/LaunchAgents/
        - `launchctl list` 能查到 label
        """
        plist_exists = self.config.launchd_plist_path.is_file()
        if plist_exists:
            return True
        # 再查 launchctl list（plist 已加载但文件被删的情况）
        return self._in_launchctl_list()

    def _in_launchctl_list(self) -> bool:
        """`launchctl list` 是否包含本 label。"""
        try:
            result = subprocess.run(
                ["launchctl", "list"],
                capture_output=True,
                check=True,
            )
        except (subprocess.CalledProcessError, OSError) as e:
            logger.debug("launchctl list 调用失败：{}", e)
            return False
        stdout = result.stdout.decode("utf-8", errors="replace")
        return self.config.label in stdout
