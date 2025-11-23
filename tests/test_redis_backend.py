import asyncio
import itertools

import pytest
import redis.asyncio as redis

from aiofreqlimit import FreqLimit
from aiofreqlimit.backends.redis import RedisBackend
from aiofreqlimit.params import FreqLimitParams


@pytest.mark.asyncio
async def test_redis_backend_enforces_spacing(redis_freq_limit: FreqLimit) -> None:
    """
    Integration: real Redis container + RedisBackend inside FreqLimit.

    params: limit=5, period=1s => interval ~0.2 s.
    Several concurrent reservations for the same key must be spread out.
    """

    limiter = redis_freq_limit
    loop = asyncio.get_running_loop()

    times: list[float] = []

    async def worker() -> None:
        async with limiter.resource("key"):
            times.append(loop.time())

    _ = await asyncio.gather(*(worker() for _ in range(5)))

    assert len(times) == 5
    times.sort()

    # Interval is ~0.2s; allow generous cushion for Docker jitter.
    assert all(b - a >= 0.1 for a, b in itertools.pairwise(times))


@pytest.mark.asyncio
async def test_redis_backend_clear_cleans_keys(redis_backend: RedisBackend) -> None:
    """clear() removes limiter keys so tests don't leak state."""

    backend = redis_backend

    params = FreqLimitParams(limit=2, period=1.0)
    limiter = FreqLimit(params, backend=backend)

    async with limiter.resource("key1"):
        pass
    async with limiter.resource("key2"):
        pass

    await backend.clear()


@pytest.mark.asyncio
async def test_redis_backend_first_reserve_has_zero_delay(
    redis_backend: RedisBackend,
) -> None:
    """First reservation on a cold key is immediate (no debt)."""
    params = FreqLimitParams(limit=2, period=1.0)

    delay = await redis_backend.reserve("k", now=0.0, params=params)

    assert delay == 0.0


@pytest.mark.asyncio
async def test_redis_backend_second_reserve_has_spacing(
    redis_backend: RedisBackend,
) -> None:
    """Second immediate call should wait about one interval."""
    params = FreqLimitParams(limit=2, period=1.0)

    _ = await redis_backend.reserve("k2", now=0.0, params=params)
    delay2 = await redis_backend.reserve("k2", now=0.0, params=params)

    assert 0.1 <= delay2 <= 1.0  # ~interval (0.5s) with some jitter margin


@pytest.mark.asyncio
async def test_redis_backend_burst_allows_free_tokens(
    redis_backend: RedisBackend,
) -> None:
    """Burst tokens are free; the next request waits (tests tau)."""
    params = FreqLimitParams(limit=5, period=1.0, burst=3)

    delays = [
        await redis_backend.reserve("burst", now=0.0, params=params) for _ in range(3)
    ]
    delay4 = await redis_backend.reserve("burst", now=0.0, params=params)

    assert all(d <= 0.05 for d in delays)  # burst tokens should be free
    assert delay4 > 0.05  # next one should wait


@pytest.mark.asyncio
async def test_redis_backend_sets_ttl_with_buffer(
    redis_backend: RedisBackend, redis_client: redis.Redis
) -> None:
    """TTL ~ interval+extra_ttl; checks Lua TTL math."""
    params = FreqLimitParams(limit=1, period=1.0)

    _ = await redis_backend.reserve("ttl", now=0.0, params=params)

    ttl = await redis_client.ttl("test:freqlimit:ttl")

    assert ttl is not None
    assert 1 <= ttl <= 3  # interval (1s) + extra_ttl (1s) ~= 2s


@pytest.mark.asyncio
async def test_redis_backend_ttl_equals_interval_plus_extra(
    redis_backend: RedisBackend, redis_client: redis.Redis
) -> None:
    """TTL не должна превышать interval + extra_ttl для limit=1."""

    params = FreqLimitParams(limit=1, period=1.0)

    _ = await redis_backend.reserve("ttl_exact", now=0.0, params=params)

    ttl = await redis_client.ttl("test:freqlimit:ttl_exact")

    assert ttl is not None
    assert (
        1 <= ttl <= 2
    )  # expected ~2s (ceil), anything higher means double-counted TTL


@pytest.mark.asyncio
async def test_redis_backend_ttl_not_inflated_by_tau(
    redis_backend: RedisBackend, redis_client: redis.Redis
) -> None:
    """Tau (burst slack) не должен увеличивать TTL."""

    params = FreqLimitParams(limit=2, period=2.0, burst=2)  # interval=1s, tau=1s

    _ = await redis_backend.reserve("ttl_tau", now=0.0, params=params)

    ttl = await redis_client.ttl("test:freqlimit:ttl_tau")

    assert ttl is not None
    assert 1 <= ttl <= 2  # still ~interval (1s) + extra_ttl (1s)


@pytest.mark.asyncio
async def test_redis_backend_clear_keeps_foreign_keys(
    redis_backend: RedisBackend,
    redis_client: redis.Redis,
) -> None:
    """clear() must not delete non-prefixed keys."""
    _ = await redis_client.set("foreign", "1")

    _ = await redis_backend.reserve(
        "own", now=0.0, params=FreqLimitParams(limit=1, period=1.0)
    )
    await redis_backend.clear()

    assert await redis_client.get("foreign") == "1"


@pytest.mark.asyncio
async def test_redis_backend_accepts_none_key(
    redis_backend: RedisBackend, redis_client: redis.Redis
) -> None:
    """None key should be accepted and stored under prefix."""

    params = FreqLimitParams(limit=1, period=1.0)

    delay = await redis_backend.reserve(None, now=0.0, params=params)

    assert delay == 0.0
    ttl = await redis_client.ttl("test:freqlimit:None")
    assert ttl is not None
    assert ttl >= 1
