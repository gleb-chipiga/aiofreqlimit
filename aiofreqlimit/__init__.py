import asyncio
from contextlib import asynccontextmanager, contextmanager, suppress
from typing import AsyncGenerator, Dict, Final, Generator, Hashable, Optional

__all__ = ('FreqLimit', '__version__')
__version__ = '0.0.2'

import attr


@attr.s(auto_attribs=True)
class Lock:
    count: int = 0
    ts: float = -float('inf')
    lock: asyncio.Lock = attr.ib(factory=asyncio.Lock,
                                 on_setattr=attr.setters.frozen)


class FreqLimit:

    def __init__(self, interval: float, clean_interval: float = 0) -> None:
        if interval <= 0:
            raise RuntimeError('Interval must be greater than 0')
        if clean_interval < 0:
            raise RuntimeError('Clean interval must be greater than '
                               'or equal to 0')
        self._interval: Final[float] = interval
        self._clean_interval: Final[float] = (
            clean_interval if clean_interval > 0 else interval)
        self._locks: Final[Dict[Hashable, Lock]] = {}
        self._clean_event: Final = asyncio.Event()
        self._clean_task: Optional[asyncio.Task[None]] = None
        self._loop: Final = asyncio.get_running_loop()

    async def clear(self) -> None:
        if self._clean_task is not None:
            self._clean_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._clean_task
            self._clean_task = None
        self._locks.clear()
        self._clean_event.clear()

    @asynccontextmanager
    async def acquire(
        self, key: Hashable = None
    ) -> AsyncGenerator[None, None]:
        if self._clean_task is None:
            self._clean_task = asyncio.create_task(self._clean())
        if key not in self._locks:
            self._locks[key] = Lock()
        with self._count(key):
            async with self._locks[key].lock:
                delay = (self._interval - self._loop.time() +
                         self._locks[key].ts)
                if delay > 0:
                    await asyncio.sleep(delay)
                self._locks[key].ts = self._loop.time()
                yield

    @contextmanager
    def _count(self, key: Hashable) -> Generator[None, None, None]:
        assert key in self._locks
        self._locks[key].count += 1
        yield
        self._locks[key].count -= 1
        if self._locks[key].count == 0:
            self._clean_event.set()

    async def _clean(self) -> None:
        while True:
            if len(self._locks) == 0:
                await self._clean_event.wait()
                self._clean_event.clear()
            for key in tuple(self._locks):
                age = self._loop.time() - self._locks[key].ts
                if self._locks[key].count == 0 and age >= self._clean_interval:
                    del self._locks[key]
            await asyncio.sleep(self._clean_interval)
