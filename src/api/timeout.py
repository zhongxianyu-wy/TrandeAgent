"""请求级超时保护（P1-1 修复）。

为什么：fund_service 的 list_funds / get_fund_detail / get_nav 等方法直接调用
DataProvider，后者会触发 AkShare 真实网络请求。AkShare 无内置超时，一旦上游
响应慢，整个 API 请求会无限期挂起，前端基金列表/详情页卡死。

怎么做：用 ThreadPoolExecutor + future.result(timeout=...) 把同步阻塞调用
包装成可超时操作。超时后返回降级结果（空列表 / NotFoundError），
保证 API 在默认 8 秒内必返回。

不影响测试：测试用 dependency_overrides 注入 mock，不走本包装。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Any, Callable, TypeVar

from loguru import logger

T = TypeVar("T")

# 单独的线程池（避免阻塞事件循环；同步 IO 放线程里跑）
_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="api-timeout")

# 默认超时（秒）。AkShare 单次请求通常 1-3s，8s 兜底。
DEFAULT_TIMEOUT = 8.0


def call_with_timeout(
    fn: Callable[..., T],
    *args: Any,
    timeout: float = DEFAULT_TIMEOUT,
    **kwargs: Any,
) -> T:
    """在独立线程执行同步函数，超时抛 TimeoutError。

    Args:
        fn: 同步可调用对象（通常是 provider 方法）。
        *args, **kwargs: 传给 fn 的参数。
        timeout: 超时秒数。

    Raises:
        TimeoutError: 超时（未完成的线程继续在后台跑，但不阻塞调用方）。
    """
    future = _executor.submit(fn, *args, **kwargs)
    try:
        return future.result(timeout=timeout)
    except FutureTimeout as exc:
        logger.warning("调用 {} 超时（{}s）", getattr(fn, "__name__", fn), timeout)
        raise TimeoutError(
            f"数据源响应超时（{timeout}s），请稍后重试或检查缓存"
        ) from exc


__all__ = ["call_with_timeout", "DEFAULT_TIMEOUT"]
