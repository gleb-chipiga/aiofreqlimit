import asyncio
from contextlib import suppress
from random import uniform
from typing import List, Tuple, cast
from weakref import ref

import pytest
from hypothesis import given
from hypothesis.strategies import floats
from pytest_mock import MockerFixture

import aiofreqlimit


@pytest.mark.asyncio
async def test_lock_context_manager_enter(mocker: MockerFixture) -> None:
    lock = aiofreqlimit.Lock()

    acquire = mocker.patch.object(lock._lock, "acquire")
    acquire.side_effect = RuntimeError("acquire")
    release = mocker.patch.object(lock._lock, "release")
    flag = False
    with pytest.raises(RuntimeError, match="acquire"):
        async with lock:
            flag = True
    assert lock.count == 1
    acquire.assert_called_once_with()
    release.assert_not_called()
    assert not flag


@pytest.mark.asyncio
async def test_lock_context_manager_exit(mocker: MockerFixture) -> None:
    lock = aiofreqlimit.Lock()

    acquire = mocker.patch.object(lock._lock, "acquire")
    release = mocker.patch.object(lock._lock, "release")
    release.side_effect = RuntimeError("release")
    flag = False
    with pytest.raises(RuntimeError, match="release"):
        async with lock:
            flag = True
    assert lock.count == 0
    acquire.assert_called_once_with()
    release.assert_called_once_with()
    assert flag


@pytest.mark.asyncio
async def test_lock_context_manager() -> None:
    lock = aiofreqlimit.Lock()

    async with lock:
        assert lock.count == 1
    assert lock.count == 0

    with suppress(RuntimeError):
        async with lock:
            assert lock.count == 1
            raise RuntimeError()
    assert lock.count == 0


@given(interval=floats(max_value=0))
def test_freq_limit_interval(interval: float) -> None:
    with pytest.raises(RuntimeError, match="Interval must be greater than 0"):
        aiofreqlimit.FreqLimit(interval)


@given(
    interval=floats(min_value=0, exclude_min=True),
    clean_interval=floats(max_value=0, exclude_max=True),
)
def test_freq_limit_clean_interval(
    interval: float, clean_interval: float
) -> None:
    with pytest.raises(
        RuntimeError,
        match="Clean interval must be greater than or equal to 0",
    ):
        aiofreqlimit.FreqLimit(interval, clean_interval)


@pytest.mark.asyncio
async def test_freq_limit() -> None:
    freq_limit = aiofreqlimit.FreqLimit(0.1)
    loop = asyncio.get_running_loop()
    time_marks = Tuple[float, float, float]

    async def limit(
        _freq_limit: aiofreqlimit.FreqLimit, interval: float
    ) -> time_marks:
        time1 = loop.time()
        async with _freq_limit.resource("key"):
            assert tuple(freq_limit._locks) == ("key",)
            time2 = loop.time()
            await asyncio.sleep(interval)
            time3 = loop.time()
        return time2, time3, time2 - time1

    tasks = (limit(freq_limit, uniform(0, 0.1)) for _ in range(5))
    intervals = cast(List[time_marks], await asyncio.gather(*tasks))
    assert all(isinstance(value, tuple) for value in intervals)
    intervals = sorted(intervals, key=lambda interval: interval[0])
    for i in range(len(intervals)):
        if i + 1 < len(intervals):
            assert intervals[i + 1][0] - intervals[i][0] > 0.1
            assert intervals[i][1] < intervals[i + 1][0]

    await asyncio.sleep(0.11)
    assert tuple(freq_limit._locks) == ()

    async with freq_limit.resource("key"):
        pass
    assert tuple(freq_limit._locks) == ("key",)
    await asyncio.sleep(0.33)
    assert tuple(freq_limit._locks) == ()

    await freq_limit.clear()
    assert freq_limit._clean_task is None
    assert tuple(freq_limit._locks) == ()
    assert not freq_limit._clean_event.is_set()


@pytest.mark.asyncio
async def test_freq_limit_keys() -> None:
    freq_limit = aiofreqlimit.FreqLimit(0.1)
    assert tuple(freq_limit._locks) == ()
    async with freq_limit.resource("key2"):
        assert tuple(freq_limit._locks.keys()) == ("key2",)
        async with freq_limit.resource("key3"):
            assert tuple(freq_limit._locks.keys()) == ("key2", "key3")
            async with freq_limit.resource("key4"):
                assert tuple(freq_limit._locks.keys()) == (
                    "key2",
                    "key3",
                    "key4",
                )
        await asyncio.sleep(0.11)
        assert tuple(freq_limit._locks.keys()) == ("key2",)
    await asyncio.sleep(0.11)
    assert tuple(freq_limit._locks) == ()
    await freq_limit.clear()


@pytest.mark.asyncio
async def test_freq_limit_overlaps() -> None:
    async def task1(_freq_limit: aiofreqlimit.FreqLimit) -> None:
        async with _freq_limit.resource("key1"):
            assert tuple(_freq_limit._locks) == ("key1",)
            await asyncio.sleep(0.11)
            assert tuple(_freq_limit._locks) == ("key1", "key2")

    async def task2(_freq_limit: aiofreqlimit.FreqLimit) -> None:
        await asyncio.sleep(0.05)
        assert tuple(_freq_limit._locks) == ("key1",)
        async with _freq_limit.resource("key2"):
            assert tuple(_freq_limit._locks) == ("key1", "key2")
            await asyncio.sleep(0.16)
            assert tuple(_freq_limit._locks) == ("key2", "key3")

    async def task3(_freq_limit: aiofreqlimit.FreqLimit) -> None:
        await asyncio.sleep(0.21)
        assert tuple(_freq_limit._locks) == ("key2",)
        async with _freq_limit.resource("key3"):
            assert tuple(_freq_limit._locks) == ("key2", "key3")
            lock2_ref = ref(_freq_limit._locks["key2"])
            async with _freq_limit.resource("key2"):
                assert tuple(_freq_limit._locks) == ("key2", "key3")
                assert lock2_ref() is _freq_limit._locks["key2"]
                await asyncio.sleep(0.1)
            assert tuple(_freq_limit._locks) == ("key2", "key3")
            await asyncio.sleep(0.1)
            assert lock2_ref() is None
            assert tuple(_freq_limit._locks) == ("key3",)
        assert tuple(_freq_limit._locks) == ("key3",)
        await asyncio.sleep(0.1)
        assert tuple(_freq_limit._locks) == ()

    freq_limit = aiofreqlimit.FreqLimit(0.1)
    await asyncio.gather(
        task1(freq_limit), task2(freq_limit), task3(freq_limit)
    )
    await freq_limit.clear()


@pytest.mark.asyncio
async def test_freq_limit_frequency() -> None:
    loop = asyncio.get_running_loop()
    intervals: List[float] = []
    time = loop.time()
    freq_limit = aiofreqlimit.FreqLimit(0.05)
    lock_ref = None
    for index in range(10):
        async with freq_limit.resource("key"):
            pass
        if index == 0:
            lock_ref = ref(freq_limit._locks["key"])
        else:
            intervals.append(loop.time() - time)
            assert lock_ref is not None
            assert lock_ref() is freq_limit._locks["key"]
        time = loop.time()
        assert "key" in freq_limit._locks
    assert all(0.05 <= interval <= 0.051 for interval in intervals)
    await freq_limit.clear()
