import os
from collections.abc import AsyncIterator, Callable, Iterator
from importlib import import_module
from pathlib import Path
from types import TracebackType
from typing import Protocol, cast

import pytest
import redis.asyncio as redis

from aiofreqlimit import FreqLimit, FreqLimitParams
from aiofreqlimit.backends.redis import RedisBackend, RedisClientProtocol


class _RedisContainerProto(Protocol):
    def __enter__(self) -> "_RedisContainerProto": ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None: ...

    def get_container_host_ip(self) -> str: ...
    def get_exposed_port(self, port: int | str) -> str: ...


# Dynamically import testcontainers.redis to avoid missing-stub errors.
RedisContainer = cast(
    type[_RedisContainerProto],
    import_module("testcontainers.redis").RedisContainer,
)


def _ensure_docker_host_env() -> None:
    """Set DOCKER_HOST to a reachable Docker socket.

    Tries rootless/Podman/Colima/classic paths; fails fast otherwise.
    """

    if os.environ.get("DOCKER_HOST"):
        return

    uid = os.getuid()
    candidates = [
        f"unix:///run/user/{uid}/docker.sock",  # rootless Docker
        f"unix:///run/user/{uid}/podman/podman.sock",  # Podman Docker API
        f"unix://{Path.home()}/.colima/default/docker.sock",  # Colima
        "unix:///var/run/docker.sock",  # classic Docker
    ]

    tried: list[str] = []
    for url in candidates:
        sock_path = url.removeprefix("unix://")
        tried.append(sock_path)
        if Path(sock_path).exists():
            os.environ["DOCKER_HOST"] = url
            return

    paths = ", ".join(tried)
    raise RuntimeError(f"Docker socket not found; set DOCKER_HOST. Tried: {paths}")


@pytest.fixture(scope="session")
def redis_url() -> Iterator[str]:
    """Start a real Redis in Docker and yield its URL."""

    _ensure_docker_host_env()

    container = cast(_RedisContainerProto, cast(object, RedisContainer()))
    with container:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(6379)
        yield f"redis://{host}:{port}/0"


@pytest.fixture
async def redis_client(redis_url: str) -> AsyncIterator[RedisClientProtocol]:
    """Async redis client talking to the container."""

    redis_from_url = cast(
        Callable[..., RedisClientProtocol],
        redis.Redis.from_url,
    )
    client = redis_from_url(redis_url, decode_responses=True)
    _ = await client.ping()
    try:
        yield client
    finally:
        _ = await client.aclose()


@pytest.fixture
async def redis_backend(
    redis_client: RedisClientProtocol,
) -> AsyncIterator[RedisBackend]:
    """RedisBackend for integration tests, cleaned around each test."""

    backend = RedisBackend(
        redis_client,
        prefix="test:freqlimit:",
        extra_ttl=1.0,
    )
    await backend.clear()
    try:
        yield backend
    finally:
        await backend.clear()


@pytest.fixture
def redis_freq_limit(redis_backend: RedisBackend) -> FreqLimit:
    """FreqLimit configured to use the live Redis backend."""

    params = FreqLimitParams(limit=5, period=1.0, burst=1)
    return FreqLimit(params, backend=redis_backend)
