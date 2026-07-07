"""运行状态存储（plan §2 / T03 / T06）。

维护两个文件：
- `last_run.json`：最近一次运行的元信息（覆盖写）
- `run_history.jsonl`：每次运行一条记录（追加写）

每次运行通过 `record_run` 同时更新两者。
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger


def _now_iso() -> str:
    """当前 UTC 时间 ISO 字符串（带时区）。"""
    return datetime.now(timezone.utc).isoformat()


class StateStore:
    """last_run / run_history 读写。"""

    def __init__(self, last_run_file: Path, run_history_file: Path) -> None:
        self.last_run_file = last_run_file
        self.run_history_file = run_history_file

    # ---- last_run.json ----

    def load_last_run(self) -> dict[str, Any] | None:
        """读取 last_run.json，不存在或损坏返回 None。"""
        if not self.last_run_file.is_file():
            return None
        try:
            return json.loads(self.last_run_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("last_run.json 解析失败，视为无记录：{}", e)
            return None

    def save_last_run(
        self,
        last_run_date: date,
        last_run_at: str,
        last_status: str,
        last_duration_sec: int,
    ) -> None:
        """覆盖写 last_run.json（plan §2）。"""
        self.last_run_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "last_run_date": last_run_date.isoformat(),
            "last_run_at": last_run_at,
            "last_status": last_status,
            "last_duration_sec": last_duration_sec,
        }
        self.last_run_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ---- run_history.jsonl ----

    def append_history(
        self,
        run_at: str,
        status: str,
        duration_sec: int,
        mode: str,
        *,
        fund_count: int | None = None,
        error: str | None = None,
    ) -> None:
        """追加一条记录到 run_history.jsonl（plan §2）。

        Args:
            run_at: 运行时间 ISO 字符串。
            status: 运行状态（success / failed / partial）。
            duration_sec: 耗时（秒）。
            mode: 运行模式（daily / force / backfill / dry_run）。
            fund_count: 处理基金数（可选）。
            error: 失败原因（可选）。
        """
        self.run_history_file.parent.mkdir(parents=True, exist_ok=True)
        record: dict[str, Any] = {
            "run_at": run_at,
            "status": status,
            "duration_sec": duration_sec,
            "mode": mode,
        }
        if fund_count is not None:
            record["fund_count"] = fund_count
        if error is not None:
            record["error"] = error
        with open(self.run_history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def read_history(self, limit: int | None = None) -> list[dict[str, Any]]:
        """读取 run_history.jsonl，返回记录列表（最旧→最新）。

        跳过损坏行。limit 给定时返回最新 limit 条（保持时序）。
        """
        if not self.run_history_file.is_file():
            return []
        records: list[dict[str, Any]] = []
        for line in self.run_history_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                logger.warning("run_history.jsonl 跳过损坏行：{!r}", line[:80])
        if limit is not None and limit >= 0:
            records = records[-limit:] if limit else []
        return records

    # ---- 组合操作 ----

    def record(
        self,
        status: str,
        duration_sec: int,
        mode: str,
        *,
        run_at: str | None = None,
        run_date: date | None = None,
        fund_count: int | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        """记录本次运行：同时更新 last_run.json 与 run_history.jsonl。

        Args:
            status: 运行状态。
            duration_sec: 耗时（秒）。
            mode: 运行模式。
            run_at: 运行时间 ISO；None 取当前时间。
            run_date: 运行日期；None 取今天。
            fund_count: 处理基金数（可选）。
            error: 失败原因（可选）。

        Returns:
            写入 run_history 的记录字典。
        """
        run_at = run_at or _now_iso()
        run_date = run_date or date.today()
        self.save_last_run(run_date, run_at, status, duration_sec)
        self.append_history(
            run_at,
            status,
            duration_sec,
            mode,
            fund_count=fund_count,
            error=error,
        )
        record = {
            "run_at": run_at,
            "status": status,
            "duration_sec": duration_sec,
            "mode": mode,
        }
        if fund_count is not None:
            record["fund_count"] = fund_count
        if error is not None:
            record["error"] = error
        return record
