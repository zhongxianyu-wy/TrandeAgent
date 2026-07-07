"""性能基准测试（T15）。

要求：查询 API P95 ≤ 500ms。在 mock 注入下，端到端响应时间应远低于此阈值。
本测试对关键查询端点连续打多次请求，统计 P95，并断言不超标。
"""
from __future__ import annotations

import statistics
import time

# P95 阈值（毫秒）
P95_THRESHOLD_MS = 500
# 每端点采样次数
SAMPLES = 30


def _percentile(values: list[float], pct: float) -> float:
    """简易百分位计算。"""
    if not values:
        return 0.0
    s = sorted(values)
    k = int(round((pct / 100.0) * (len(s) - 1)))
    return s[k]


def test_perf_fund_list(client):
    latencies = []
    for _ in range(SAMPLES):
        t0 = time.perf_counter()
        r = client.get("/api/funds?size=20")
        dt = (time.perf_counter() - t0) * 1000
        assert r.status_code == 200
        latencies.append(dt)
    p95 = _percentile(latencies, 95)
    assert p95 <= P95_THRESHOLD_MS, f"funds list P95={p95:.1f}ms > {P95_THRESHOLD_MS}ms"


def test_perf_fund_detail(client):
    latencies = []
    for _ in range(SAMPLES):
        t0 = time.perf_counter()
        r = client.get("/api/funds/000001")
        dt = (time.perf_counter() - t0) * 1000
        assert r.status_code == 200
        latencies.append(dt)
    p95 = _percentile(latencies, 95)
    assert p95 <= P95_THRESHOLD_MS, f"fund detail P95={p95:.1f}ms > {P95_THRESHOLD_MS}ms"


def test_perf_fund_nav(client):
    latencies = []
    for _ in range(SAMPLES):
        t0 = time.perf_counter()
        r = client.get("/api/funds/000001/nav?size=250")
        dt = (time.perf_counter() - t0) * 1000
        assert r.status_code == 200
        latencies.append(dt)
    p95 = _percentile(latencies, 95)
    assert p95 <= P95_THRESHOLD_MS, f"fund nav P95={p95:.1f}ms > {P95_THRESHOLD_MS}ms"


def test_perf_strategies_list(client):
    latencies = []
    for _ in range(SAMPLES):
        t0 = time.perf_counter()
        r = client.get("/api/strategies")
        dt = (time.perf_counter() - t0) * 1000
        assert r.status_code == 200
        latencies.append(dt)
    p95 = _percentile(latencies, 95)
    assert p95 <= P95_THRESHOLD_MS, f"strategies P95={p95:.1f}ms > {P95_THRESHOLD_MS}ms"


def test_perf_system_status(client):
    latencies = []
    for _ in range(SAMPLES):
        t0 = time.perf_counter()
        r = client.get("/api/system/status")
        dt = (time.perf_counter() - t0) * 1000
        assert r.status_code == 200
        latencies.append(dt)
    p95 = _percentile(latencies, 95)
    assert p95 <= P95_THRESHOLD_MS, f"system status P95={p95:.1f}ms > {P95_THRESHOLD_MS}ms"


def test_perf_summary_report(client):
    """汇总报告：打印各端点 P95（不阻断，仅信息）。"""
    endpoints = [
        "/api/funds",
        "/api/funds/000001",
        "/api/funds/000001/nav",
        "/api/strategies",
        "/api/system/status",
        "/api/system/health",
    ]
    print("\n=== 性能基准 P95（ms） ===")
    for ep in endpoints:
        lat = []
        for _ in range(SAMPLES):
            t0 = time.perf_counter()
            client.get(ep)
            lat.append((time.perf_counter() - t0) * 1000)
        p95 = _percentile(lat, 95)
        print(f"  {ep:32s} P50={statistics.median(lat):6.1f}  P95={p95:6.1f}")
        assert p95 <= P95_THRESHOLD_MS
