"""定时调度层（Feature #3 scheduler）。

基于 macOS launchd 的日频调度：
- 交易日过滤（chinese_calendar）
- 漏推送检测与补发（上限 5 个交易日）
- 运行状态记录（last_run.json + run_history.jsonl）

下游所有业务模块通过 main.py 编排，调度层只负责"何时触发"。
"""
from src.scheduler.config import SchedulerConfig, load_scheduler_config
from src.scheduler.holiday import is_trading_day
from src.scheduler.scheduler import Scheduler
from src.scheduler.launchd_scheduler import LaunchdScheduler
from src.scheduler.state import StateStore

__all__ = [
    "Scheduler",
    "LaunchdScheduler",
    "SchedulerConfig",
    "load_scheduler_config",
    "is_trading_day",
    "StateStore",
]
