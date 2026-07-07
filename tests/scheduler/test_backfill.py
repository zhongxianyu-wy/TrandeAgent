"""T04/T05: detect_missed_runs + backfill 单元测试（plan §5 / spec FR-3）。

today 注入为 2026-07-07（周二，交易日），使用已知 chinese_calendar 数据。
"""
from __future__ import annotations

from datetime import date

import pytest

from src.scheduler.config import SchedulerConfig
from src.scheduler.launchd_scheduler import LaunchdScheduler

TODAY = date(2026, 7, 7)  # 周二，交易日


def _make_scheduler(tmp_path, *, last_run_date=None, backfill_max_days=5, runner=None):
    """构造 today=2026-07-07 的 scheduler，可选预置 last_run。"""
    cfg = SchedulerConfig(
        state_dir=str(tmp_path / "state"),
        project_root=str(tmp_path),
        backfill_max_days=backfill_max_days,
    )
    cfg.state_path.mkdir(parents=True, exist_ok=True)
    sched = LaunchdScheduler(cfg, state_dir=cfg.state_path, today=TODAY, runner=runner)
    if last_run_date is not None:
        sched.state.save_last_run(last_run_date, f"{last_run_date}T16:00:00+08:00", "success", 100)
    return sched


class TestDetectMissedRuns:
    def test_no_history_returns_empty(self, tmp_path):
        sched = _make_scheduler(tmp_path)
        assert sched.detect_missed_runs() == []

    def test_same_day_returns_empty(self, tmp_path):
        sched = _make_scheduler(tmp_path, last_run_date=date(2026, 7, 7))
        assert sched.detect_missed_runs() == []

    def test_one_trading_day_gap(self, tmp_path):
        # 上次 07-06(周一)，today 07-07：中间无交易日 → []
        sched = _make_scheduler(tmp_path, last_run_date=date(2026, 7, 6))
        assert sched.detect_missed_runs() == []

    def test_cross_weekend_one_missed(self, tmp_path):
        # 上次 07-03(周五)，today 07-07：(07-03,07-07) → [07-06]
        sched = _make_scheduler(tmp_path, last_run_date=date(2026, 7, 3))
        assert sched.detect_missed_runs() == [date(2026, 7, 6)]

    def test_three_trading_days_gap(self, tmp_path):
        # 上次 06-30(周二)，today 07-07：(06-30,07-07) → [07-01,07-02,07-03,07-06]
        sched = _make_scheduler(tmp_path, last_run_date=date(2026, 6, 30))
        assert sched.detect_missed_runs() == [
            date(2026, 7, 1), date(2026, 7, 2), date(2026, 7, 3), date(2026, 7, 6),
        ]

    def test_capped_to_max_days(self, tmp_path):
        # 上次 06-25(周四)，today 07-07：漏 7 天，截断到最近 5 天
        # (06-25,07-07) → [06-26,06-29,06-30,07-01,07-02,07-03,07-06] (7)
        # 截断最后 5 → [06-30,07-01,07-02,07-03,07-06]
        sched = _make_scheduler(tmp_path, last_run_date=date(2026, 6, 25), backfill_max_days=5)
        missed = sched.detect_missed_runs()
        assert len(missed) == 5
        assert missed == [date(2026, 6, 30), date(2026, 7, 1), date(2026, 7, 2), date(2026, 7, 3), date(2026, 7, 6)]

    def test_corrupt_last_run_returns_empty(self, tmp_path):
        sched = _make_scheduler(tmp_path)
        sched.state.last_run_file.write_text("{bad json", encoding="utf-8")
        assert sched.detect_missed_runs() == []

    def test_invalid_last_run_date_returns_empty(self, tmp_path):
        """last_run_date 非法 ISO 字符串时视为无漏推送（覆盖 except 分支）。"""
        sched = _make_scheduler(tmp_path)
        sched.state.save_last_run(date(2026, 7, 7), "t", "success", 1)
        # 篡改 last_run_date 为非法值
        import json
        data = json.loads(sched.state.last_run_file.read_text(encoding="utf-8"))
        data["last_run_date"] = "not-a-date"
        sched.state.last_run_file.write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )
        assert sched.detect_missed_runs() == []

    def test_clock_skew_last_in_future_returns_empty(self, tmp_path):
        # last_run_date 在未来 → 视为无漏推送
        sched = _make_scheduler(tmp_path, last_run_date=date(2026, 7, 10))
        assert sched.detect_missed_runs() == []


class TestBackfill:
    def test_empty_dates_noop(self, tmp_path):
        calls = []
        sched = _make_scheduler(tmp_path, runner=lambda d, m: (calls.append((d, m)), ("success", 1, 0))[1])
        sched.backfill([])
        assert calls == []

    def test_backfill_calls_runner_per_date(self, tmp_path):
        calls = []
        def runner(d, mode):
            calls.append((d, mode))
            return ("success", 10, 5)
        sched = _make_scheduler(tmp_path, runner=runner)
        dates = [date(2026, 7, 1), date(2026, 7, 2)]
        sched.backfill(dates)
        assert calls == [(date(2026, 7, 1), "backfill"), (date(2026, 7, 2), "backfill")]

    def test_backfill_records_history(self, tmp_path):
        def runner(d, mode):
            return ("success", 20, 42)
        sched = _make_scheduler(tmp_path, runner=runner)
        sched.backfill([date(2026, 7, 1), date(2026, 7, 2)])
        hist = sched.state.read_history()
        assert len(hist) == 2
        assert all(r["mode"] == "backfill" for r in hist)
        assert all(r["status"] == "success" for r in hist)

    def test_backfill_truncates_over_limit(self, tmp_path):
        """plan §6：补发上限 5 天，超出只补最近 N 天。"""
        calls = []
        def runner(d, mode):
            calls.append(d)
            return ("success", 1, 0)
        sched = _make_scheduler(tmp_path, backfill_max_days=5, runner=runner)
        # 给 8 天
        dates = [date(2026, 6, x) for x in range(20, 28)]
        sched.backfill(dates)
        # 只调用最后 5 个 runner
        assert len(calls) == 5
        assert calls == dates[-5:]

    def test_backfill_runner_exception_records_failed(self, tmp_path):
        def runner(d, mode):
            raise RuntimeError("boom")
        sched = _make_scheduler(tmp_path, runner=runner)
        sched.backfill([date(2026, 7, 1), date(2026, 7, 2)])
        hist = sched.state.read_history()
        assert len(hist) == 2
        assert all(r["status"] == "failed" for r in hist)
        assert all(r["error"] == "boom" for r in hist)
