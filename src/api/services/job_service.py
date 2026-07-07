"""任务服务（T09 核心）。

JobStore 维护 in-memory dict + SQLite 持久化（表 ``api_jobs``），重启后可查。
后台任务由 FastAPI BackgroundTasks 驱动，执行业务函数后更新状态。

设计要点：
- 表 api_jobs 字段对齐 :class:`Job`，以 JSON 文本存储 result。
- create/update/get/list 全部同步（SQLite 专用连接 + Lock）。
- 业务执行函数 ``run_*`` 供 BackgroundTasks 调用，内部捕获异常写入 job.error。
"""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from loguru import logger

from src.api.schema import Job, JobStatus


def _utcnow() -> datetime:
    """timezone-aware UTC 当前时间。"""
    return datetime.now(timezone.utc)


# SQLite 建表 DDL
_API_JOBS_DDL = """
CREATE TABLE IF NOT EXISTS api_jobs (
    job_id       TEXT PRIMARY KEY,
    type         TEXT NOT NULL,
    status       TEXT NOT NULL,
    progress     REAL DEFAULT 0,
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    result       TEXT,
    error        TEXT
);
"""


class JobStore:
    """任务存储：in-memory dict + SQLite 持久化。"""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._cache: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        if db_path is not None:
            self._open(db_path)

    # ----- SQLite -----
    def _open(self, db_path: str | Path) -> None:
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(path), check_same_thread=False, isolation_level=None
        )
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute(_API_JOBS_DDL)
        # 启动时把已持久化的任务加载进内存
        self._load_all_from_db()

    def _row_to_job(self, row: sqlite3.Row) -> Job:
        result_raw = row["result"]
        return Job(
            job_id=row["job_id"],
            type=row["type"],
            status=JobStatus(row["status"]),
            progress=float(row["progress"] or 0.0),
            started_at=datetime.fromisoformat(row["started_at"]),
            finished_at=(
                datetime.fromisoformat(row["finished_at"])
                if row["finished_at"]
                else None
            ),
            result=json.loads(result_raw) if result_raw else None,
            error=row["error"],
        )

    def _persist(self, job: Job) -> None:
        if self._conn is None:
            return
        with self._lock:
            self._conn.execute(
                (
                    "INSERT INTO api_jobs "
                    "(job_id, type, status, progress, started_at, finished_at, result, error) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(job_id) DO UPDATE SET "
                    "type=excluded.type, status=excluded.status, progress=excluded.progress, "
                    "started_at=excluded.started_at, finished_at=excluded.finished_at, "
                    "result=excluded.result, error=excluded.error"
                ),
                (
                    job.job_id,
                    job.type,
                    job.status.value,
                    job.progress,
                    job.started_at.isoformat(),
                    job.finished_at.isoformat() if job.finished_at else None,
                    json.dumps(job.result, ensure_ascii=False) if job.result else None,
                    job.error,
                ),
            )

    def _load_all_from_db(self) -> None:
        if self._conn is None:
            return
        with self._lock:
            cur = self._conn.execute("SELECT * FROM api_jobs")
            for row in cur.fetchall():
                self._cache[row["job_id"]] = self._row_to_job(row)

    # ----- 对外 API -----
    def create_job(self, job_type: str, params: Optional[dict] = None) -> Job:
        """创建一条 pending 任务并持久化。params 仅记录到内存（不落库）。"""
        job = Job(
            job_id=uuid.uuid4().hex[:12],
            type=job_type,
            status=JobStatus.pending,
            progress=0.0,
            started_at=_utcnow(),
        )
        self._cache[job.job_id] = job
        self._persist(job)
        logger.info("创建任务 {} (type={})", job.job_id, job_type)
        return job

    def update_job(self, job_id: str, **fields: Any) -> Optional[Job]:
        """部分更新任务字段并持久化。"""
        job = self._cache.get(job_id)
        if job is None:
            return None
        data = job.model_dump()
        data.update(fields)
        if "status" in fields and isinstance(fields["status"], str):
            data["status"] = JobStatus(fields["status"])
        updated = Job(**data)
        self._cache[job_id] = updated
        self._persist(updated)
        return updated

    def get_job(self, job_id: str) -> Optional[Job]:
        return self._cache.get(job_id)

    def list_jobs(
        self, status: Optional[JobStatus] = None, limit: int = 50
    ) -> list[Job]:
        jobs = list(self._cache.values())
        if status is not None:
            jobs = [j for j in jobs if j.status == status]
        jobs.sort(key=lambda j: j.started_at, reverse=True)
        return jobs[:limit]

    def count_active(self) -> int:
        return sum(
            1 for j in self._cache.values() if j.status in (JobStatus.pending, JobStatus.running)
        )

    def close(self) -> None:
        if self._conn is not None:
            with self._lock:
                self._conn.close()
            self._conn = None


# ---------------------------------------------------------------------------
# 后台任务执行器（供 BackgroundTasks 调用）
# ---------------------------------------------------------------------------
def _execute(
    store: JobStore,
    job_id: str,
    func: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> None:
    """通用执行器：置 running → 调 func → 置 succeeded/failed。

    func 若返回 dict 则记为 result；func 可通过回调上报进度。
    """
    store.update_job(job_id, status=JobStatus.running, progress=0.0)
    try:
        result = func(*args, **kwargs)
        payload: Optional[dict] = None
        if isinstance(result, dict):
            payload = result
        elif result is not None and hasattr(result, "model_dump"):
            payload = result.model_dump(mode="json")
        store.update_job(
            job_id,
            status=JobStatus.succeeded,
            progress=1.0,
            finished_at=_utcnow(),
            result=payload,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("任务 {} 执行失败", job_id)
        store.update_job(
            job_id,
            status=JobStatus.failed,
            finished_at=_utcnow(),
            error=str(exc),
        )


def run_refresh_data(store: JobStore, job_id: str, provider: Any) -> None:
    """数据刷新任务。"""
    _execute(store, job_id, provider.refresh_incremental)


def run_backtest(
    store: JobStore,
    job_id: str,
    arena_pipeline: Any,
    count: int = 50,
) -> None:
    """策略回测/竞技场任务。"""
    _execute(store, job_id, arena_pipeline.run, count=count, write_base=False)


def run_analyze(store: JobStore, job_id: str, analyzer: Any, fund_code: str) -> None:
    """单基金 AI 分析任务。"""
    _execute(store, job_id, analyzer.analyze, fund_code)


def run_batch_analyze(
    store: JobStore,
    job_id: str,
    analyzer: Any,
    fund_codes: list[str],
) -> None:
    """批量分析任务，逐只分析并汇总。"""

    def _batch() -> dict:
        reports = {}
        for i, code in enumerate(fund_codes, 1):
            reports[code] = analyzer.analyze(code).model_dump(mode="json")
            store.update_job(job_id, progress=i / max(len(fund_codes), 1))
        return {"analyzed": len(reports), "codes": list(reports.keys())}

    _execute(store, job_id, _batch)


def run_regenerate(
    store: JobStore,
    job_id: str,
    arena_pipeline: Any,
    count: int = 50,
) -> None:
    """策略重新生成任务。"""
    run_backtest(store, job_id, arena_pipeline, count=count)


__all__ = [
    "JobStore",
    "run_refresh_data",
    "run_backtest",
    "run_analyze",
    "run_batch_analyze",
    "run_regenerate",
]
