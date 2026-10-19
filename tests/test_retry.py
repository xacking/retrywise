import asyncio

import pytest

from retrywise import RetryError, backoff_delays, retry


def no_sleep(_):
    return None


async def async_no_sleep(_):
    return None


def test_succeeds_after_failures():
    calls = []

    @retry(3, sleep=no_sleep)
    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise ConnectionError("boom")
        return "ok"

    assert flaky() == "ok"
    assert len(calls) == 3


def test_gives_up():
    @retry(2, sleep=no_sleep)
    def bad():
        raise TimeoutError("slow")

    with pytest.raises(RetryError) as info:
        bad()
    assert info.value.attempts == 2
    assert isinstance(info.value.last, TimeoutError)


def test_reraise_and_filters():
    @retry(5, on=ValueError, sleep=no_sleep, reraise=True)
    def wrong_type():
        raise KeyError("x")

    with pytest.raises(KeyError):
        wrong_type()

    seen = []

    @retry(5, retry_if=lambda e: "retry" in str(e), on_retry=lambda n, e, d: seen.append(n), sleep=no_sleep)
    def maybe():
        raise RuntimeError("fatal")

    with pytest.raises(RuntimeError):
        maybe()
    assert seen == []


def test_async():
    calls = []

    @retry(3, sleep=async_no_sleep)
    async def flaky():
        calls.append(1)
        if len(calls) < 2:
            raise OSError
        return 42

    assert asyncio.run(flaky()) == 42


def test_delays():
    assert list(backoff_delays(5, base=1, jitter=False, max_delay=5)) == [1, 2, 4, 5]
