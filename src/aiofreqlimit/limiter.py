import asyncio
import inspect
from collections.abc import AsyncIterator, Awaitable, Callable, Hashable
from contextlib import asynccontextmanager
from typing import Final

from .backends import FreqLimitBackend
from .params import FreqLimitParams

__all__ = ("FreqLimit",)


class FreqLimit:
    """
    Async rate limiter built on the Generic Cell Rate Algorithm (GCRA).

    Example:

        params = FreqLimitParams(limit=1, period=1.0)  # 1 опер/сек
        limiter = FreqLimit(params, backend=InMemoryBackend())

        async with limiter.resource("chat:42"):
            await send_message(...)
    """

    # Alias so one can write FreqLimit.Params(...)
    Params: type[FreqLimitParams] = FreqLimitParams

    def __init__(
        self,
        params: FreqLimitParams,
        *,
        backend: FreqLimitBackend,
    ) -> None:
        self._params: Final = params
        self._backend: Final = backend

    @property
    def params(self) -> FreqLimitParams:
        return self._params

    @property
    def backend(self) -> FreqLimitBackend:
        return self._backend

    @asynccontextmanager
    async def resource(self, key: Hashable | None = None) -> AsyncIterator[None]:
        """
        Context manager that enforces the limit.

        key=None — global bucket (single key for whole limiter).
        """
        if key is None:
            key = "_global"

        loop = asyncio.get_running_loop()
        now = loop.time()
        delay = await self._backend.reserve(key, now, self._params)
        if delay > 0:
            await asyncio.sleep(delay)
        yield

    async def clear(self) -> None:
        """
        Reset backend state if supported.
        For InMemoryBackend — clears data.
        """
        clear_obj: Callable[[], Awaitable[object] | object] | None = getattr(
            self._backend,
            "clear",
            None,
        )
        if clear_obj is None:
            return

        result = clear_obj()
        if inspect.isawaitable(result):
            await result
