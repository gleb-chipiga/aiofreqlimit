from __future__ import annotations

# pyright: reportPrivateUsage=false
import math

import pytest

from aiofreqlimit.backends.memory import InMemoryBackend
from aiofreqlimit.params import FreqLimitParams


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
