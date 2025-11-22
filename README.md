# aiofreqlimit — Async GCRA rate limiter

[![Latest PyPI package version](https://badge.fury.io/py/aiofreqlimit.svg)](https://pypi.org/project/aiofreqlimit)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Downloads](https://img.shields.io/pypi/dm/aiofreqlimit)](https://pypistats.org/packages/aiofreqlimit)

Async rate limiting for Python 3.11+ built on the Generic Cell Rate Algorithm (GCRA) with
type-safe parameters and pluggable backends.

## Installation

```bash
pip install aiofreqlimit
```

## Quickstart

Create a contract (`FreqLimitParams`), choose a backend, and wrap your code with the
async context manager:

```python
import asyncio

from aiofreqlimit import FreqLimit, FreqLimitParams
from aiofreqlimit.backends.memory import InMemoryBackend

params = FreqLimitParams(limit=1, period=1.0, burst=1)  # 1 op / second
limiter = FreqLimit(params, backend=InMemoryBackend())


async def send_message(chat_id: int, text: str) -> None:
    async with limiter.resource(f"chat:{chat_id}"):
        await bot.send_message(chat_id, text)


async def main() -> None:
    await asyncio.gather(*(send_message(42, f"msg {i}") for i in range(5)))


asyncio.run(main())
```

- `key` is any hashable; `None` uses a global bucket.
- `burst` lets you allow short bursts without changing the long-term rate.

## Params are type-safe

You can keep your limits as constants and reuse them across the project:

```python
from aiofreqlimit import FreqLimitParams

TELEGRAM_PER_CHAT = FreqLimitParams(limit=1, period=1.0, burst=1)
TELEGRAM_PER_GROUP = FreqLimitParams(limit=20, period=60.0, burst=3)
```

## Backends

- `InMemoryBackend` (in-process, single event loop) — import from
  `aiofreqlimit.backends.memory`.
  - `idle_ttl: float | None` — drop idle keys after this many seconds (default: None).
  - `sweeper_interval: float | None` — optional background cleanup period; set to
    enable a sweeper task (default: None).
- Implement `FreqLimitBackend` to plug in Redis/DB/etc.:

```python
from collections.abc import Hashable
from aiofreqlimit import FreqLimitBackend, FreqLimitParams


class RedisBackend(FreqLimitBackend):
    async def reserve(self, key: Hashable, now: float, params: FreqLimitParams) -> float:
        ...
```

`FreqLimit` requires an explicit backend instance; no default is provided.

## Testing

The library ships with pytest + hypothesis tests. To run them with uv:

```bash
uv run pytest tests
```

## License

MIT
