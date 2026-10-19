"""Retry with exponential backoff and jitter, for sync and async functions."""

from __future__ import annotations

import asyncio
import functools
import inspect
import logging
import random
import time
from collections.abc import Callable
from typing import Any, TypeVar

__all__ = ["retry", "RetryError", "backoff_delays"]
__version__ = "0.1.0"

F = TypeVar("F", bound=Callable[..., Any])
log = logging.getLogger("retrywise")


class RetryError(Exception):
    """Raised when all attempts fail. The last exception is available as `.last` and `__cause__`."""

    def __init__(self, attempts: int, last: BaseException):
        super().__init__(f"Gave up after {attempts} attempts: {last!r}")
        self.attempts = attempts
        self.last = last


def backoff_delays(attempts: int, base: float = 0.5, factor: float = 2.0, max_delay: float = 30.0, jitter: bool = True):
    """Yield the sleep before each retry (attempts - 1 values)."""
    for i in range(attempts - 1):
        delay = min(max_delay, base * factor**i)
        yield random.uniform(0, delay) if jitter else delay


def retry(
    attempts: int = 3,
    *,
    on: type[BaseException] | tuple[type[BaseException], ...] = Exception,
    base: float = 0.5,
    factor: float = 2.0,
    max_delay: float = 30.0,
    jitter: bool = True,
    retry_if: Callable[[BaseException], bool] | None = None,
    on_retry: Callable[[int, BaseException, float], None] | None = None,
    reraise: bool = False,
    sleep: Callable[[float], Any] | None = None,
) -> Callable[[F], F]:
    """Decorator that retries a function when it raises.

    attempts: total tries including the first one.
    on: exception type(s) that trigger a retry; anything else propagates immediately.
    retry_if: extra predicate on the exception (e.g. only retry HTTP 5xx).
    on_retry: callback(attempt_number, exception, delay) before sleeping.
    reraise: raise the original exception instead of RetryError at the end.
    """
    if attempts < 1:
        raise ValueError("attempts must be >= 1")

    def should_retry(exc: BaseException) -> bool:
        return isinstance(exc, on) and (retry_if is None or retry_if(exc))

    def give_up(n: int, exc: BaseException):
        if reraise:
            raise exc
        raise RetryError(n, exc) from exc

    def decorator(fn: F) -> F:
        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args, **kwargs):
                delays = backoff_delays(attempts, base, factor, max_delay, jitter)
                for n in range(1, attempts + 1):
                    try:
                        return await fn(*args, **kwargs)
                    except BaseException as exc:  # noqa: BLE001
                        if not should_retry(exc):
                            raise
                        if n == attempts:
                            give_up(n, exc)
                        delay = next(delays)
                        log.debug("retry %s/%s after %.2fs: %r", n, attempts, delay, exc)
                        if on_retry:
                            on_retry(n, exc, delay)
                        await (sleep or asyncio.sleep)(delay)

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            delays = backoff_delays(attempts, base, factor, max_delay, jitter)
            for n in range(1, attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except BaseException as exc:  # noqa: BLE001
                    if not should_retry(exc):
                        raise
                    if n == attempts:
                        give_up(n, exc)
                    delay = next(delays)
                    log.debug("retry %s/%s after %.2fs: %r", n, attempts, delay, exc)
                    if on_retry:
                        on_retry(n, exc, delay)
                    (sleep or time.sleep)(delay)

        return wrapper  # type: ignore[return-value]

    return decorator
