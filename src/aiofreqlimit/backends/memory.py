from __future__ import annotations

# pyright: reportPrivateUsage=false
import asyncio
import contextlib
from collections.abc import Hashable

from aiofreqlimit.gcra import gcra_step
from aiofreqlimit.params import FreqLimitParams

__all__ = ("InMemoryBackend",)


class InMemoryBackend:
    """
    In-process backend: single event loop / single process.

    For each key keeps:
      * _tat[key]   — current TAT per GCRA
      * _locks[key] — asyncio.Lock to serialize key traffic
    """

    def __init__(
        self,
        *,
        idle_ttl: float | None = None,
        sweeper_interval: float | None = None,
    ) -> None:
        if idle_ttl is not None and idle_ttl <= 0:
            msg = "idle_ttl must be positive or None"
            raise ValueError(msg)
        if sweeper_interval is not None and sweeper_interval <= 0:
            msg = "sweeper_interval must be positive or None"
            raise ValueError(msg)
        self._tat: dict[Hashable, float] = {}
        self._locks: dict[Hashable, asyncio.Lock] = {}
        self._last_seen: dict[Hashable, float] = {}
        self._idle_ttl: float | None = idle_ttl
        self._sweeper_interval: float | None = sweeper_interval
        self._sweeper_task: asyncio.Task[None] | None = None

    async def reserve(
        self,
        key: Hashable,
        now: float,
        params: FreqLimitParams,
    ) -> float:
        if self._idle_ttl is not None:
            self._cleanup_expired(now)
        self._ensure_sweeper()

        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock

        async with lock:
            tat = self._tat.get(key)
            new_tat, delay = gcra_step(now, tat, params)
            self._tat[key] = new_tat
            self._last_seen[key] = now
            return delay

    async def clear(self) -> None:
        """Reset state (handy in tests or manual reset)."""
        self._tat.clear()
        self._locks.clear()
        self._last_seen.clear()
        if self._sweeper_task is not None:
            _ = self._sweeper_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._sweeper_task
            self._sweeper_task = None

    def _cleanup_expired(self, now: float) -> None:
        ttl = self._idle_ttl
        if ttl is None:
            return
        expiry_threshold = now - ttl
        for key in list(self._tat):
            last_seen = self._last_seen.get(key)
            if last_seen is None or last_seen > expiry_threshold:
                continue
            lock = self._locks.get(key)
            if lock is not None and lock.locked():
                continue
            _ = self._tat.pop(key, None)
            _ = self._locks.pop(key, None)
            _ = self._last_seen.pop(key, None)

    def _ensure_sweeper(self) -> None:
        interval = self._sweeper_interval
        if interval is None:
            return
        if self._sweeper_task is not None and not self._sweeper_task.done():
            return
        loop = asyncio.get_running_loop()
        self._sweeper_task = loop.create_task(self._sweep_periodically(interval))

    async def _sweep_periodically(self, interval: float) -> None:
        try:
            while True:
                await asyncio.sleep(interval)
                now = asyncio.get_running_loop().time()
                self._cleanup_expired(now)
        except asyncio.CancelledError:  # pragma: no cover - lifecycle cleanup
            raise
