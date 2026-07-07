"""Scheduler 抽象接口（plan §3 / T01）。

定义调度层的统一契约，具体实现由 `LaunchdScheduler` 提供。
下游模块只依赖本抽象，便于迁云时替换实现（spec §7）。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date


class Scheduler(ABC):
    """调度器抽象基类。"""

    @abstractmethod
    def should_run_today(self, today: date) -> bool:
        """判定今日是否应运行（交易日过滤）。

        Args:
            today: 待判定的日期。

        Returns:
            True 表示是 A 股交易日，应运行主流程。
        """

    @abstractmethod
    def detect_missed_runs(self) -> list[date]:
        """检测漏推送的交易日列表。

        读取 last_run.json 上次运行日期，计算其与今天之间漏掉的交易日，
        结果最多包含 `backfill_max_days` 个（plan §6 决策）。

        Returns:
            漏掉的交易日列表（升序，不含上次运行日与今天）。
        """

    @abstractmethod
    def backfill(self, dates: list[date]) -> None:
        """补发指定日期的报告。

        对超过 `backfill_max_days` 的部分截断（只补最近 N 天）。

        Args:
            dates: 待补发的日期列表。
        """

    @abstractmethod
    def record_run(self, status: str, duration_sec: int, mode: str) -> None:
        """记录本次运行到历史（last_run.json + run_history.jsonl）。

        Args:
            status: 运行状态（success / failed / partial）。
            duration_sec: 本次运行耗时（秒）。
            mode: 运行模式（daily / force / backfill / dry_run）。
        """
