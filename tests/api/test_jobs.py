"""jobs 路由测试（T09，FR-6）。"""
from __future__ import annotations

from datetime import datetime, timezone

from src.api import deps
from src.api.schema import Job, JobStatus
from src.api.services.job_service import (
    JobStore,
    run_analyze,
    run_backtest,
    run_batch_analyze,
    run_refresh_data,
    run_regenerate,
)


def test_refresh_data_job(client):
    r = client.post("/api/jobs/refresh-data")
    assert r.status_code == 200
    job_id = r.json()["data"]["job_id"]
    r2 = client.get(f"/api/jobs/{job_id}")
    assert r2.status_code == 200
    assert r2.json()["data"]["status"] == "succeeded"


def test_backtest_job(client):
    r = client.post("/api/jobs/backtest", json={"count": 5})
    assert r.status_code == 200
    job_id = r.json()["data"]["job_id"]
    r2 = client.get(f"/api/jobs/{job_id}")
    assert r2.json()["data"]["status"] == "succeeded"


def test_analyze_job(client):
    r = client.post("/api/jobs/analyze", json={"fund_codes": ["000001"]})
    assert r.status_code == 200
    job_id = r.json()["data"]["job_id"]
    r2 = client.get(f"/api/jobs/{job_id}")
    assert r2.json()["data"]["status"] == "succeeded"
    assert r2.json()["data"]["result"]["analyzed"] == 1


def test_get_job_not_found(client):
    r = client.get("/api/jobs/nonexistent")
    assert r.status_code == 404


def test_list_jobs(client):
    client.post("/api/jobs/refresh-data")
    client.post("/api/jobs/refresh-data")
    r = client.get("/api/jobs")
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    assert len(items) >= 2


def test_list_jobs_filter_status(client):
    client.post("/api/jobs/refresh-data")
    r = client.get("/api/jobs?status=succeeded")
    assert r.status_code == 200
    for j in r.json()["data"]["items"]:
        assert j["status"] == "succeeded"


def test_backtest_default_count(client):
    """不带 body 触发默认 count。"""
    r = client.post("/api/jobs/backtest")
    assert r.status_code == 200
    job_id = r.json()["data"]["job_id"]
    assert client.get(f"/api/jobs/{job_id}").json()["data"]["status"] == "succeeded"


# ---------------------------------------------------------------------------
# JobStore 单元测试（含 SQLite 持久化）
# ---------------------------------------------------------------------------
def test_job_store_in_memory_crud(tmp_path):
    store = JobStore()  # 纯内存
    job = store.create_job("analyze")
    assert job.status == JobStatus.pending
    updated = store.update_job(job.job_id, status=JobStatus.running, progress=0.5)
    assert updated.status == JobStatus.running
    assert updated.progress == 0.5
    assert store.get_job(job.job_id).progress == 0.5
    assert store.count_active() == 1
    jobs = store.list_jobs()
    assert len(jobs) == 1
    assert store.update_job("nope", status=JobStatus.failed) is None


def test_job_store_sqlite_persistence(tmp_path):
    db = tmp_path / "jobs.db"
    store1 = JobStore(db)
    job = store1.create_job("backtest")
    store1.update_job(job.job_id, status=JobStatus.succeeded, progress=1.0)
    store1.close()

    # 新 store 从 SQLite 恢复
    store2 = JobStore(db)
    restored = store2.get_job(job.job_id)
    assert restored is not None
    assert restored.status == JobStatus.succeeded
    assert restored.progress == 1.0


def test_run_function_records_failure(tmp_path):
    store = JobStore(tmp_path / "f.db")

    def boom():
        raise ValueError("爆炸")

    job = store.create_job("analyze")
    run_analyze.__wrapped__ if hasattr(run_analyze, "__wrapped__") else None
    # 直接调用 _execute 路径
    from src.api.services.job_service import _execute

    _execute(store, job.job_id, boom)
    failed = store.get_job(job.job_id)
    assert failed.status == JobStatus.failed
    assert "爆炸" in failed.error


def test_run_refresh_data_success(tmp_path):
    store = JobStore(tmp_path / "r.db")
    provider = type("P", (), {"refresh_incremental": lambda self: {"ok": 1}})()
    job = store.create_job("refresh-data")
    run_refresh_data(store, job.job_id, provider)
    assert store.get_job(job.job_id).status == JobStatus.succeeded


def test_run_backtest_success(tmp_path):
    store = JobStore(tmp_path / "b.db")
    pipe = type("P", (), {"run": lambda self, **k: {"strategies": 5}})()
    job = store.create_job("backtest")
    run_backtest(store, job.job_id, pipe, count=5)
    assert store.get_job(job.job_id).status == JobStatus.succeeded


def test_run_regenerate_success(tmp_path):
    store = JobStore(tmp_path / "g.db")
    pipe = type("P", (), {"run": lambda self, **k: {"strategies": 5}})()
    job = store.create_job("regenerate")
    run_regenerate(store, job.job_id, pipe, count=5)
    assert store.get_job(job.job_id).status == JobStatus.succeeded


def test_run_batch_analyze_progress(tmp_path):
    store = JobStore(tmp_path / "ba.db")
    analyzer = type(
        "A",
        (),
        {
            "analyze": lambda self, code: type(
                "R", (), {"model_dump": lambda self, **k: {"code": code}}
            )()
        },
    )()
    job = store.create_job("analyze")
    run_batch_analyze(store, job.job_id, analyzer, ["000001", "161725"])
    done = store.get_job(job.job_id)
    assert done.status == JobStatus.succeeded
    assert done.result["analyzed"] == 2
