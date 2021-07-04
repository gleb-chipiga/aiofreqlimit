import asyncio
from contextlib import (AsyncExitStack, asynccontextmanager, contextmanager,
                        suppress)
from typing import (AsyncContextManager, AsyncIterator, ContextManager, Dict,
                    Final, Hashable, Iterator, Optional, cast)

__all__ = ('FreqLimit', '__version__')
__version__ = '0.0.4'

import attr


@attr.s(auto_attribs=True)
class Lock:
    count: int = attr.ib(default=0, init=False)
    ts: float = attr.ib(default=-float('inf'), init=False)
    lock: asyncio.Lock = attr.ib(init=False, factory=asyncio.Lock,
                                 on_setattr=attr.setters.frozen)

    @contextmanager
    def count_context(self) -> Iterator[None]:
        self.count += 1
        try:
            yield
        finally:
            self.count -= 1


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

    @asynccontextmanager
    async def acquire(
        self, key: Hashable = None
    ) -> AsyncIterator[None]:
        if self._clean_task is None:
            self._clean_task = asyncio.create_task(self._clean())
        if key not in self._locks:
            self._locks[key] = Lock()
        async with AsyncExitStack() as stack:
            stack.callback(self._clean_event.set)
            stack.enter_context(
                cast(ContextManager[None], self._locks[key].count_context()))
            await stack.enter_async_context(
                cast(AsyncContextManager[None], self._locks[key].lock))
            delay = self._interval - self._loop.time() + self._locks[key].ts
            if delay > 0:
                await asyncio.sleep(delay)
            self._locks[key].ts = self._loop.time()
            yield

    async def clear(self) -> None:
        if self._clean_task is not None:
            self._clean_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._clean_task
            self._clean_task = None
        self._locks.clear()
        self._clean_event.clear()

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
