from __future__ import annotations

from collections.abc import Hashable
from typing import Protocol, runtime_checkable

from aiofreqlimit.params import FreqLimitParams

__all__ = ("FreqLimitBackend",)


@runtime_checkable
class FreqLimitBackend(Protocol):
    async def reserve(
        self,
        key: Hashable,
        now: float,
        params: FreqLimitParams,
    ) -> float:
        """
        Reserve a slot for `key` at moment `now`.

        Must:
          * read current state (TAT etc.),
          * update it,
          * return delay in seconds (0.0 means run now).
        """
        ...
