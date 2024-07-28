===========================================
Frequency limit context manager for asyncio
===========================================

.. image:: https://badge.fury.io/py/aiofreqlimit.svg
   :target: https://pypi.org/project/aiofreqlimit
   :alt: Latest PyPI package version

.. image:: https://img.shields.io/badge/license-MIT-blue.svg
   :target: https://github.com/gleb-chipiga/aiofreqlimit/blob/master/LICENSE
   :alt: License

.. image:: https://img.shields.io/pypi/dm/aiofreqlimit
   :target: https://pypistats.org/packages/aiofreqlimit
   :alt: Downloads count

Installation
============
aiofreqlimit requires Python 3.11 or greater and is available on PyPI. Use pip to install it:

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