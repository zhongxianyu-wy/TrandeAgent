"""重试策略（plan §3.2 / FR-6）。

用 tenacity 实现指数退避（1-2-4s），3 次失败后抛 `UpstreamUnavailable`，
由调用方决定是否降级到缓存。
"""
from __future__ import annotations

from typing import Any, Callable, TypeVar

from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

T = TypeVar("T")


class UpstreamUnavailable(Exception):
    """上游接口连续重试后仍不可用。

    调用方捕获后应降级到缓存，并在新鲜度报告标记 is_stale=True。
    """


def build_retry_decorator(
    max_attempts: int = 3,
    backoff_base: float = 1.0,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """构造指数退避重试装饰器。

    Args:
        max_attempts: 最大尝试次数（含首次）。
        backoff_base: 退避基数；实际等待 = backoff_base * 2^(attempt-1)，
            即 base=1 时序列 1, 2, 4。

    Returns:
        可直接 `@` 应用的装饰器。
    """

    def _log_retry(state: RetryCallState) -> None:
        from loguru import logger

        exc = state.outcome.exception() if state.outcome else None
        logger.warning(
            "上游调用失败，第 {n}/{max} 次重试（等待 {wait:.1f}s）：{exc}",
            n=state.attempt_number,
            max=max_attempts,
            wait=state.next_action.sleep if state.next_action else 0,
            exc=repr(exc),
        )

    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=backoff_base, exp_base=2, min=backoff_base),
        retry=retry_if_exception_type(Exception),
        before_sleep=_log_retry,
        reraise=True,
    )


def with_retry(
    func: Callable[..., T],
    *args: Any,
    max_attempts: int = 3,
    backoff_base: float = 1.0,
    **kwargs: Any,
) -> T:
    """以函数式方式调用带重试的逻辑。

    超过重试次数后抛 `UpstreamUnavailable`（包装底层异常）。
    """
    decorator = build_retry_decorator(max_attempts, backoff_base)
    try:
        return decorator(func)(*args, **kwargs)
    except Exception as exc:
        raise UpstreamUnavailable(
            f"{func.__name__} 重试 {max_attempts} 次后仍失败：{exc!r}"
        ) from exc
