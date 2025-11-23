from collections.abc import Callable, Iterable
from types import TracebackType
from typing import Generic, TypeVar, overload

T = TypeVar("T")

class ApproxBase(float): ...

def approx(
    expected: float | complex | Iterable[float | complex],
    *,
    rel: float | None = ...,  # relative tolerance
    abs: float | None = ...,  # absolute tolerance
    nan_ok: bool = False,
) -> ApproxBase: ...

class _MarkDecorator:
    def __call__(self, obj: T) -> T: ...
    def __getattr__(self, name: str) -> _MarkDecorator: ...
    def parametrize(
        self,
        argnames: str | Iterable[str],
        argvalues: Iterable[object],
        ids: Iterable[str] | None = ...,
    ) -> Callable[[T], T]: ...
    def asyncio(self, obj: T) -> T: ...

mark: _MarkDecorator

@overload
def fixture(func: T) -> T: ...
@overload
def fixture(
    *,
    scope: str | None = ...,
    params: list[object] | None = ...,
    autouse: bool = False,
    name: str | None = ...,
) -> Callable[[T], T]: ...

class _RaisesContext(Generic[T]):
    def __enter__(self) -> T: ...
    def __exit__(
        self,
        __exc_type: type[BaseException] | None,
        __exc: BaseException | None,
        __tb: TracebackType | None,
        /,
    ) -> bool | None: ...

def raises(
    expected_exception: type[BaseException] | tuple[type[BaseException], ...],
    match: str | None = ...,
) -> _RaisesContext[BaseException]: ...
def parametrize(
    argnames: str | Iterable[str],
    argvalues: Iterable[object],
    ids: Iterable[str] | None = ...,
) -> Callable[[T], T]: ...
