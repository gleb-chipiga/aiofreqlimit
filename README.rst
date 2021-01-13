About
=====
Frequency limit context manager for asyncio.

Installation
============
aiofreqlimit requires Python 3.8 or greater and is available on PyPI. Use pip to install it:

.. code-block:: bash

    pip install aiofreqlimit

Using aiofreqlimit
==================
Pass a value of any hashable type to `acquire` or do not specify any parameter:

.. code-block:: python

    import asyncio

    from aiofreqlimit import FreqLimit

    limit = FreqLimit(1 / 10)


    async def job():
        async with limit.acquire('some_key'):
            await some_call()


    async def main():
        await asyncio.gather(job() for _ in range(100))


    asyncio.run(main())