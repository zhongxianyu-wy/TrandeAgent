"""调度层配置加载（Pydantic）。

对应 config/scheduler.yaml，参考 src/data/config.py 的加载模式。
"""
from __future__ import annotations

from pathlib import Path

import yaml
from loguru import logger
from pydantic import BaseModel, Field, field_validator


# 项目根目录（src/scheduler/config.py → 上溯两级）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# 默认配置文件查找路径
_DEFAULT_CONFIG_PATHS = (
    Path("config/scheduler.yaml"),
    _PROJECT_ROOT / "config" / "scheduler.yaml",
)


class SchedulerConfig(BaseModel):
    """调度层配置（对应 config/scheduler.yaml）。"""

    trigger_time: str = "16:00"  # HH:MM，launchd StartCalendarInterval
    timezone: str = "Asia/Shanghai"
    backfill_max_days: int = 5  # 漏推送补发上限（plan §6）
    holidays_source: str = "chinese_calendar"  # 备选: custom
    state_dir: str = "data/state"  # last_run.json / run_history.jsonl 目录
    label: str = "com.trandeagent.daily"  # launchd Label
    project_root: str = str(_PROJECT_ROOT)  # plist WorkingDirectory
    # launchd ProgramArguments 入口（spec FR-1：python -m src.main daily）
    program_module: str = "src.main"
    program_command: str = "daily"
    # 显式 PATH（spec §5 macOS 兼容：含 python / lark-cli 路径）
    env_path: str = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
    log_dir: str = "logs"

    @field_validator("trigger_time")
    @classmethod
    def _validate_time(cls, v: str) -> str:
        parts = v.split(":")
        if len(parts) != 2:
            raise ValueError(f"trigger_time 应为 HH:MM 格式，得到 {v!r}")
        h, m = int(parts[0]), int(parts[1])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError(f"trigger_time 时分越界：{v!r}")
        return v

    @field_validator("backfill_max_days")
    @classmethod
    def _validate_max_days(cls, v: int) -> int:
        if v < 1:
            raise ValueError("backfill_max_days 必须 >= 1")
        return v

    # ---- 派生属性 ----

    @property
    def hour(self) -> int:
        return int(self.trigger_time.split(":")[0])

    @property
    def minute(self) -> int:
        return int(self.trigger_time.split(":")[1])

    @property
    def state_path(self) -> Path:
        return Path(self.state_dir)

    @property
    def last_run_file(self) -> Path:
        return self.state_path / "last_run.json"

    @property
    def run_history_file(self) -> Path:
        return self.state_path / "run_history.jsonl"

    @property
    def plist_filename(self) -> str:
        return f"{self.label}.plist"

    @property
    def launchd_plist_path(self) -> Path:
        """~/Library/LaunchAgents/{label}.plist"""
        return Path.home() / "Library" / "LaunchAgents" / self.plist_filename

    @property
    def working_dir(self) -> Path:
        return Path(self.project_root)

    @property
    def stdout_log(self) -> Path:
        return self.working_dir / self.log_dir / "launchd.out.log"

    @property
    def stderr_log(self) -> Path:
        return self.working_dir / self.log_dir / "launchd.err.log"


def load_scheduler_config(path: str | Path | None = None) -> SchedulerConfig:
    """加载调度层配置。

    Args:
        path: 指定 yaml 路径；None 时按 _DEFAULT_CONFIG_PATHS 查找，找不到用默认值。

    Returns:
        SchedulerConfig 实例。
    """
    candidates = [Path(path)] if path else list(_DEFAULT_CONFIG_PATHS)
    for candidate in candidates:
        if candidate.is_file():
            with open(candidate, encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
            return SchedulerConfig(**raw)
    logger.warning("未找到 scheduler.yaml，使用默认配置（候选路径: {}）", candidates)
    return SchedulerConfig()
