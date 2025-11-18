# Frequency Limit Context Manager for asyncio

[![Latest PyPI package version](https://badge.fury.io/py/aiofreqlimit.svg)](https://pypi.org/project/aiofreqlimit)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/gleb-chipiga/aiofreqlimit/blob/master/LICENSE)
[![Downloads](https://img.shields.io/pypi/dm/aiofreqlimit)](https://pypistats.org/packages/aiofreqlimit)

## Installation

aiofreqlimit requires Python 3.11 or greater and is available on PyPI. Use pip to install it:

```bash
pip install aiofreqlimit
```

## Using aiofreqlimit

Pass a value of any hashable type to `acquire`, or omit the argument to use the default key:

```python
import asyncio

from aiofreqlimit import FreqLimit

limit = FreqLimit(1 / 10)


async def job():
    async with limit.acquire("some_key"):
        await some_call()


async def main():
    await asyncio.gather(job() for _ in range(100))


asyncio.run(main())
```
