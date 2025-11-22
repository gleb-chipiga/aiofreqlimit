from __future__ import annotations

import asyncio

import pytest

from aiofreqlimit import FreqLimit, FreqLimitParams


class SpyBackend:
    delay: float

    def __init__(self, delay: float = 0.0) -> None:
        self.delay = delay
        self.calls: list[tuple[object, float, FreqLimitParams]] = []

    async def reserve(
        self,
        key: object,
        now: float,
        params: FreqLimitParams,
    ) -> float:
        self.calls.append((key, now, params))
        return self.delay


@pytest.mark.asyncio
async def test_resource_calls_backend_with_default_key() -> None:
    params = FreqLimitParams(limit=1, period=1.0)
    backend = SpyBackend()
    limiter = FreqLimit(params, backend=backend)

    async with limiter.resource():
        pass

    assert len(backend.calls) == 1
    key, _, called_params = backend.calls[0]
    assert key == "_global"
    assert called_params is params


@pytest.mark.asyncio
async def test_resource_uses_given_key_and_params() -> None:
    params = FreqLimitParams(limit=3, period=1.0)
    backend = SpyBackend()
    limiter = FreqLimit(params, backend=backend)

    async with limiter.resource("k1"):
        pass

    assert backend.calls[0][0] == "k1"
    assert backend.calls[0][2] is params


@pytest.mark.asyncio
async def test_resource_waits_for_delay() -> None:
    params = FreqLimitParams(limit=1, period=1.0)
    backend = SpyBackend(delay=0.05)
    limiter = FreqLimit(params, backend=backend)
    loop = asyncio.get_running_loop()

    start = loop.time()
    async with limiter.resource("k2"):
        pass
    elapsed = loop.time() - start

    assert elapsed >= 0.045  # allow small jitter
