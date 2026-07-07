"""scheduler 测试公共 fixtures。"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from src.scheduler.config import SchedulerConfig
from src.scheduler.launchd_scheduler import LaunchdScheduler
from src.scheduler.state import StateStore


@pytest.fixture
def tmp_config(tmp_path: Path) -> SchedulerConfig:
    """临时 SchedulerConfig，state_dir 指向 tmp_path，避免污染真实目录。"""
    return SchedulerConfig(
        state_dir=str(tmp_path / "state"),
        project_root=str(tmp_path),
        log_dir="logs",
    )


@pytest.fixture
def state_store(tmp_path: Path) -> StateStore:
    """临时 StateStore。"""
    sdir = tmp_path / "state"
    sdir.mkdir(parents=True, exist_ok=True)
    return StateStore(
        last_run_file=sdir / "last_run.json",
        run_history_file=sdir / "run_history.jsonl",
    )


@pytest.fixture
def scheduler(tmp_config: SchedulerConfig) -> LaunchdScheduler:
    """LaunchdScheduler 实例（today 注入 + 临时 state）。

    today 默认设为 2026-07-05（周一，已知交易日，chinese_calendar 有数据）。
    各测试可自行构造新实例覆写 today。
    """
    return LaunchdScheduler(
        tmp_config,
        state_dir=tmp_config.state_path,
        today=date(2026, 7, 6),  # 周一
    )
