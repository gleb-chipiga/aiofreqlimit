import asyncio
from random import uniform
from typing import List, Tuple, cast

import pytest
from hypothesis import given
from hypothesis.strategies import floats

from aiofreqlimit import FreqLimit


@given(interval=floats(max_value=0))
def test_freq_limit_interval(interval: float) -> None:
    with pytest.raises(RuntimeError, match='Interval must be greater than 0'):
        FreqLimit(interval)


@given(interval=floats(min_value=0, exclude_min=True),
       clean_interval=floats(max_value=0, exclude_max=True))
def test_freq_limit_clean_interval(interval: float,
                                   clean_interval: float) -> None:
    with pytest.raises(RuntimeError, match='Clean interval must be greater '
                                           'than or equal to 0'):
        FreqLimit(interval, clean_interval)


@pytest.mark.asyncio
async def test_freq_limit() -> None:
    freq_limit = FreqLimit(.1, .1)
    loop = asyncio.get_running_loop()

    time_marks = Tuple[float, float, float]

    async def limit(
        _freq_limit: FreqLimit, interval: float
    ) -> time_marks:
        time1 = loop.time()
        async with _freq_limit.acquire('test'):
            time2 = loop.time()
            await asyncio.sleep(interval)
            time3 = loop.time()
            assert _freq_limit._events.keys() == _freq_limit._ts.keys()
        return time2, time3, time2 - time1

    tasks = (limit(freq_limit, uniform(0, .1)) for _ in range(5))
    intervals = cast(List[time_marks], await asyncio.gather(*tasks))
    assert all(isinstance(value, tuple) for value in intervals)
    intervals = sorted(intervals, key=lambda interval: interval[0])
    for i in range(len(intervals)):
        if i + 1 < len(intervals):
            assert intervals[i + 1][0] - intervals[i][0] > .1
            assert intervals[i][1] < intervals[i + 1][0]

    assert freq_limit._events.keys() == freq_limit._ts.keys()
    await asyncio.sleep(.2)
    assert not freq_limit._events
    await freq_limit.clear()
