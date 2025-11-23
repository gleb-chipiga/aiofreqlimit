import asyncio
import math

import pytest

from aiofreqlimit.backends.memory import InMemoryBackend
from aiofreqlimit.params import FreqLimitParams

# pyright: reportPrivateUsage=false


@pytest.mark.asyncio
async def test_reserve_sequential_spacing() -> None:
    backend = InMemoryBackend()
    params = FreqLimitParams(limit=2, period=1.0, burst=1)

    delay1 = await backend.reserve("k", now=0.0, params=params)
    assert delay1 == 0.0

    delay2 = await backend.reserve("k", now=0.0, params=params)
    assert math.isclose(delay2, 0.5, abs_tol=1e-9)

    delay3 = await backend.reserve("k", now=0.5, params=params)
    assert math.isclose(delay3, 0.5, abs_tol=1e-9)

    delay4 = await backend.reserve("k", now=1.5, params=params)
    assert math.isclose(delay4, 0.0, abs_tol=1e-9)


@pytest.mark.asyncio
async def test_clear_resets_state() -> None:
    backend = InMemoryBackend()
    params = FreqLimitParams(limit=1, period=1.0)

    _ = await backend.reserve("a", now=0.0, params=params)
    assert backend._tat

    await backend.clear()

    assert backend._tat == {}
    assert backend._locks == {}


def test_negative_ttl_and_sweeper_rejected() -> None:
    with pytest.raises(ValueError):
        _ = InMemoryBackend(idle_ttl=-1.0)

    with pytest.raises(ValueError):
        _ = InMemoryBackend(sweeper_interval=0.0)


@pytest.mark.asyncio
async def test_burst_allows_initial_free_tokens() -> None:
    backend = InMemoryBackend()
    params = FreqLimitParams(limit=2, period=1.0, burst=2)  # interval=0.5, tau=0.5

    delays = [await backend.reserve("b", now=0.0, params=params) for _ in range(2)]
    delay3 = await backend.reserve("b", now=0.0, params=params)

    assert delays == [0.0, 0.0]
    assert math.isclose(delay3, 0.5, abs_tol=1e-9)


@pytest.mark.asyncio
async def test_keys_do_not_interfere() -> None:
    backend = InMemoryBackend()
    params = FreqLimitParams(limit=1, period=1.0)

    _ = await backend.reserve("k1", now=0.0, params=params)
    delay_other = await backend.reserve("k2", now=0.0, params=params)

    assert delay_other == 0.0


@pytest.mark.asyncio
async def test_cleanup_skips_locked_key_then_removes_after_unlock() -> None:
    backend = InMemoryBackend(idle_ttl=0.01)
    key = "lockme"
    backend._tat[key] = 0.0
    backend._last_seen[key] = 0.0
    lock = asyncio.Lock()
    _ = await lock.acquire()
    backend._locks[key] = lock

    backend._cleanup_expired(now=1.0)
    assert key in backend._tat  # locked key preserved

    lock.release()
    backend._cleanup_expired(now=1.1)
    assert key not in backend._tat


@pytest.mark.asyncio
async def test_sweeper_started_and_cancelled_by_clear() -> None:
    backend = InMemoryBackend(sweeper_interval=0.01)
    params = FreqLimitParams(limit=1, period=1.0)

    _ = await backend.reserve("s", now=0.0, params=params)
    assert backend._sweeper_task is not None
    assert not backend._sweeper_task.done()

    await backend.clear()

    assert backend._sweeper_task is None


@pytest.mark.asyncio
async def test_idle_ttl_eviction() -> None:
    backend = InMemoryBackend(idle_ttl=0.05)
    params = FreqLimitParams(limit=1, period=1.0)

    _ = await backend.reserve("k1", now=0.0, params=params)
    _ = await backend.reserve("k2", now=0.0, params=params)

    # advance time beyond ttl, trigger cleanup via reserve
    _ = await backend.reserve("k1", now=0.1, params=params)

    assert "k1" in backend._tat
    assert "k2" not in backend._tat
