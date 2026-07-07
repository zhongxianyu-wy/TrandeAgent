"""T03: RateLimiter + UARotator 单元测试。"""
from __future__ import annotations

import time

import pytest

from src.data.rate_limit import RateLimiter, UARotator


class TestRateLimiter:
    def test_min_interval_enforced(self):
        """1 req/s 限速：两次 wait 间隔 >= min_interval。"""
        rl = RateLimiter(min_interval_seconds=0.5)
        t0 = time.monotonic()
        rl.wait()
        rl.wait()
        elapsed = time.monotonic() - t0
        assert elapsed >= 0.5 - 0.05  # 允许小误差

    def test_zero_interval_no_block(self):
        rl = RateLimiter(min_interval_seconds=0)
        t0 = time.monotonic()
        rl.wait()
        rl.wait()
        assert time.monotonic() - t0 < 0.1

    def test_negative_interval_rejected(self):
        with pytest.raises(ValueError):
            RateLimiter(min_interval_seconds=-1)

    def test_property(self):
        rl = RateLimiter(min_interval_seconds=2.0)
        assert rl.min_interval_seconds == 2.0


class TestUARotator:
    def test_next_returns_from_pool(self):
        pool = ["UA-A", "UA-B", "UA-C"]
        rot = UARotator(pool)
        got = {rot.next() for _ in range(10)}
        assert got <= set(pool)

    def test_cycle_loops(self):
        rot = UARotator(["X", "Y"])
        seq = [rot.next() for _ in range(5)]
        assert seq[0] == seq[2] == seq[4]  # 循环

    def test_empty_rejected(self):
        with pytest.raises(ValueError):
            UARotator([])

    def test_pool_copy_immutable(self):
        src = ["A", "B"]
        rot = UARotator(src)
        src.append("C")
        assert "C" not in rot.pool
