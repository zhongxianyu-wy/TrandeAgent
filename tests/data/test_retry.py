"""T04: RetryStrategy 单元测试。"""
from __future__ import annotations

import pytest

from src.data.retry import UpstreamUnavailable, with_retry, build_retry_decorator


def _flaky_failer(attempts_to_fail: int):
    """返回一个调用 N 次后成功的函数。"""
    state = {"calls": 0}

    def _f():
        state["calls"] += 1
        if state["calls"] <= attempts_to_fail:
            raise RuntimeError(f"fail #{state['calls']}")
        return "ok"

    return _f, state


class TestRetryStrategy:
    def test_succeeds_after_retries(self):
        f, state = _flaky_failer(2)  # 前 2 次失败，第 3 次成功
        # 装饰器版本：max_attempts=3 允许 2 次失败后第 3 次成功
        decorated = build_retry_decorator(max_attempts=3, backoff_base=0.01)(f)
        result = decorated()
        assert result == "ok"
        assert state["calls"] == 3

    def test_exhausts_attempts_raises(self):
        f, state = _flaky_failer(10)  # 永远失败
        with pytest.raises(UpstreamUnavailable):
            with_retry(f, max_attempts=3, backoff_base=0.01)
        assert state["calls"] == 3

    def test_no_retry_on_first_success(self):
        state = {"calls": 0}

        def _ok():
            state["calls"] += 1
            return "done"

        result = with_retry(_ok, max_attempts=3, backoff_base=0.01)
        assert result == "done"
        assert state["calls"] == 1

    def test_with_retry_wraps_exception(self):
        def _bad():
            raise ValueError("boom")

        with pytest.raises(UpstreamUnavailable) as exc_info:
            with_retry(_bad, max_attempts=2, backoff_base=0.01)
        assert "boom" in str(exc_info.value.__cause__)
