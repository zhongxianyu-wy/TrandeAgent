"""T03/T06: state.py 单元测试（plan §5）。

覆盖 last_run.json 读写、run_history.jsonl 追加、record 组合操作。
"""
from __future__ import annotations

import json
from datetime import date

import pytest

from src.scheduler.state import StateStore


class TestLastRun:
    def test_load_missing_returns_none(self, state_store: StateStore):
        assert state_store.load_last_run() is None

    def test_save_and_load_roundtrip(self, state_store: StateStore):
        state_store.save_last_run(
            last_run_date=date(2026, 7, 6),
            last_run_at="2026-07-06T16:00:00+08:00",
            last_status="success",
            last_duration_sec=1820,
        )
        data = state_store.load_last_run()
        assert data == {
            "last_run_date": "2026-07-06",
            "last_run_at": "2026-07-06T16:00:00+08:00",
            "last_status": "success",
            "last_duration_sec": 1820,
        }

    def test_save_creates_parent_dir(self, tmp_path):
        sdir = tmp_path / "deep" / "state"
        store = StateStore(sdir / "last_run.json", sdir / "run_history.jsonl")
        store.save_last_run(date(2026, 7, 6), "2026-07-06T16:00:00+08:00", "success", 10)
        assert store.last_run_file.is_file()

    def test_load_corrupt_returns_none(self, state_store: StateStore):
        state_store.last_run_file.write_text("not json{", encoding="utf-8")
        assert state_store.load_last_run() is None

    def test_save_overwrites(self, state_store: StateStore):
        state_store.save_last_run(date(2026, 7, 6), "t1", "success", 1)
        state_store.save_last_run(date(2026, 7, 7), "t2", "failed", 2)
        data = state_store.load_last_run()
        assert data["last_run_date"] == "2026-07-07"
        assert data["last_status"] == "failed"


class TestRunHistory:
    def test_read_empty(self, state_store: StateStore):
        assert state_store.read_history() == []

    def test_append_and_read(self, state_store: StateStore):
        state_store.append_history(
            "2026-07-06T16:00:00+08:00", "success", 1820, "daily",
            fund_count=7823,
        )
        records = state_store.read_history()
        assert len(records) == 1
        r = records[0]
        assert r["status"] == "success"
        assert r["duration_sec"] == 1820
        assert r["mode"] == "daily"
        assert r["fund_count"] == 7823

    def test_append_multiple_keeps_order(self, state_store: StateStore):
        for i in range(3):
            state_store.append_history(f"t{i}", "success", i, "daily")
        records = state_store.read_history()
        assert [r["duration_sec"] for r in records] == [0, 1, 2]

    def test_jsonl_format_one_record_per_line(self, state_store: StateStore):
        state_store.append_history("t0", "success", 1, "daily")
        state_store.append_history("t1", "failed", 2, "backfill", error="boom")
        lines = state_store.run_history_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        first = json.loads(lines[0])
        assert first["mode"] == "daily"
        second = json.loads(lines[1])
        assert second["error"] == "boom"

    def test_read_limit_returns_latest(self, state_store: StateStore):
        for i in range(5):
            state_store.append_history(f"t{i}", "success", i, "daily")
        latest = state_store.read_history(limit=2)
        assert [r["duration_sec"] for r in latest] == [3, 4]

    def test_read_skips_corrupt_lines(self, state_store: StateStore):
        state_store.run_history_file.parent.mkdir(parents=True, exist_ok=True)
        state_store.run_history_file.write_text(
            json.dumps({"run_at": "ok", "status": "success", "duration_sec": 1, "mode": "daily"}) + "\n"
            "corrupt line\n"
            + json.dumps({"run_at": "ok2", "status": "failed", "duration_sec": 2, "mode": "daily"}) + "\n",
            encoding="utf-8",
        )
        records = state_store.read_history()
        assert len(records) == 2
        assert records[0]["duration_sec"] == 1
        assert records[1]["duration_sec"] == 2

    def test_read_skips_empty_lines(self, state_store: StateStore):
        """空行应被跳过（覆盖 continue 分支）。"""
        state_store.run_history_file.parent.mkdir(parents=True, exist_ok=True)
        state_store.run_history_file.write_text(
            json.dumps({"run_at": "a", "status": "success", "duration_sec": 1, "mode": "daily"}) + "\n\n\n"
            + json.dumps({"run_at": "b", "status": "success", "duration_sec": 2, "mode": "daily"}) + "\n",
            encoding="utf-8",
        )
        records = state_store.read_history()
        assert len(records) == 2


class TestRecord:
    def test_record_updates_both_files(self, state_store: StateStore):
        record = state_store.record("success", 100, "daily", run_date=date(2026, 7, 6))
        # last_run
        last = state_store.load_last_run()
        assert last["last_run_date"] == "2026-07-06"
        assert last["last_status"] == "success"
        # history
        hist = state_store.read_history()
        assert len(hist) == 1
        assert hist[0]["mode"] == "daily"
        # 返回值
        assert record["status"] == "success"

    def test_record_with_optional_fields(self, state_store: StateStore):
        state_store.record(
            "failed", 50, "backfill",
            run_date=date(2026, 7, 5),
            fund_count=100,
            error="timeout",
        )
        last = state_store.load_last_run()
        assert last["last_duration_sec"] == 50
        hist = state_store.read_history()
        assert hist[0]["fund_count"] == 100
        assert hist[0]["error"] == "timeout"
