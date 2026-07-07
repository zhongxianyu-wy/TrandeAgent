"""限流 + User-Agent 轮换（plan §3.2 / FR-5）。

`RateLimiter` 确保 ≤ 1 req/s，线程安全；`UARotator` 在 10 个真实浏览器 UA 间循环。
组合使用：上游调用前 `rate_limiter.wait()` + `headers={"User-Agent": ua_rotator.next()}`。
"""
from __future__ import annotations

import threading
import time
from itertools import cycle


class RateLimiter:
    """令牌式最小间隔限流器（线程安全）。

    通过 `wait()` 阻塞直到距离上次放行超过 `min_interval_seconds`。
    """

    def __init__(self, min_interval_seconds: float = 1.0) -> None:
        if min_interval_seconds < 0:
            raise ValueError("min_interval_seconds 不能为负")
        self._min_interval = min_interval_seconds
        self._last_release: float = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        """阻塞直到满足限流间隔。"""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_release
            if elapsed < self._min_interval:
                sleep_for = self._min_interval - elapsed
                time.sleep(sleep_for)
            self._last_release = time.monotonic()

    @property
    def min_interval_seconds(self) -> float:
        return self._min_interval


class UARotator:
    """User-Agent 循环轮换。"""

    def __init__(self, user_agents: list[str] | None = None) -> None:
        if not user_agents:
            raise ValueError("user_agents 不能为空")
        self._pool = list(user_agents)
        self._cycle = cycle(self._pool)
        self._lock = threading.Lock()

    def next(self) -> str:
        """返回下一个 UA（线程安全）。"""
        with self._lock:
            return next(self._cycle)

    @property
    def pool(self) -> list[str]:
        return list(self._pool)
