from __future__ import annotations

from collections.abc import AsyncIterator, Hashable
from textwrap import dedent as ddent
from typing import Final, Protocol

from ..params import FreqLimitParams

__all__ = ("GCRA_LUA", "RedisBackend", "RedisClientProtocol", "ScriptProtocol")


# Local protocol copies of the minimal Redis surface we rely on.
# Mirrors the .pyi stubs we shipped, so type checkers stay happy even
# if external redis stubs are absent.
class ScriptProtocol(Protocol):
    async def __call__(self, *, keys: list[str], args: list[float]) -> str: ...


class RedisClientProtocol(Protocol):
    @classmethod
    def from_url(
        cls, url: str, *, decode_responses: bool = ...
    ) -> RedisClientProtocol: ...

    def register_script(self, script: str) -> ScriptProtocol: ...
    def scan_iter(self, *, match: str = "*") -> AsyncIterator[str]: ...
    async def delete(self, *names: str | bytes | memoryview) -> object: ...
    async def ttl(self, name: str | bytes | memoryview) -> int | float | None: ...
    async def set(self, name: str | bytes | memoryview, value: object) -> object: ...
    async def get(self, name: str | bytes | memoryview) -> object: ...
    async def ping(self) -> object: ...
    async def aclose(self) -> object: ...


# Lua script: single GCRA step + TTL handling (atomic on Redis).
#
# KEYS[1]  = key holding TAT
# ARGV[1]  = interval (T)
# ARGV[2]  = tau
# ARGV[3]  = extra_ttl (seconds)
#
# Returns string float: delay in seconds until request is conforming.
GCRA_LUA: Final[str] = ddent(
    r"""
    redis.replicate_commands()

    local key = KEYS[1]
    local interval = tonumber(ARGV[1])
    local tau = tonumber(ARGV[2])
    local extra_ttl = tonumber(ARGV[3])

    -- Current time from Redis server: seconds + microseconds
    local now_time = redis.call("TIME")
    local now = tonumber(now_time[1]) + tonumber(now_time[2]) / 1000000.0

    -- Read TAT if present
    local tat_str = redis.call("GET", key)
    local tat
    if not tat_str then
      tat = now
    else
      tat = tonumber(tat_str)
    end

    -- Earliest conforming time
    local allowed_time = tat - tau
    local delay = 0.0
    local effective_now = now

    if effective_now < allowed_time then
      delay = allowed_time - effective_now
      effective_now = allowed_time
    end

    -- GCRA virtual scheduling
    if effective_now >= tat then
      tat = effective_now + interval
    else
      tat = tat + interval
    end

    -- TTL: keep key while there is debt plus small buffer
    local ttl = (tat - now) + extra_ttl
    if ttl < 1.0 then
      ttl = 1.0
    end

    redis.call("SET", key, tat, "EX", math.ceil(ttl))

    return tostring(delay)
    """
)


class RedisBackend:
    """
    Redis backend for FreqLimit.

    GCRA logic runs in a Lua script on Redis, using server time (TIME)
    so multiple hosts share a clock. Python side only passes parameters
    and parses the resulting delay.
    """

    def __init__(
        self,
        redis: RedisClientProtocol,
        *,
        prefix: str = "freqlimit:gcra:",
        extra_ttl: float = 0.0,
    ) -> None:
        """
        redis     — redis.asyncio.Redis client.
        prefix    — prefix for limiter keys.
        extra_ttl — extra TTL buffer after backlog is cleared (seconds).
        """

        # Keep only the minimal protocol surface for type checkers.
        self._redis: Final[RedisClientProtocol] = redis
        self._prefix: Final = prefix
        self._extra_ttl: Final = float(extra_ttl)
        # Script object caches SHA and transparently uses EVAL/EVALSHA.
        self._script: ScriptProtocol = redis.register_script(GCRA_LUA)

    async def reserve(
        self,
        key: Hashable,
        now: float,
        params: FreqLimitParams,
    ) -> float:
        redis_key = f"{self._prefix}{key}"
        interval = params.interval
        tau = params.tau
        # TTL buffer after backlog is cleared; Lua adds debt duration
        extra_ttl = self._extra_ttl

        _ = now  # server time is used inside Lua script

        delay_str: str = await self._script(
            keys=[redis_key],
            args=[interval, tau, extra_ttl],
        )
        return float(delay_str)

    async def clear(self) -> None:
        """Delete keys with the prefix (handy for tests/debug)."""

        pattern = f"{self._prefix}*"
        async for key in self._redis.scan_iter(match=pattern):
            _ = await self._redis.delete(key)
