from typing import Protocol, cast

from hypothesis import given, strategies as st
from pytest import approx as _approx  # pyright: ignore[reportUnknownVariableType]

from aiofreqlimit import FreqLimitParams
from aiofreqlimit.gcra import gcra_step


class _ApproxCallable(Protocol):
    def __call__(
        self,
        expected: float,
        rel: float | None = ...,
        abs: float | None = ...,
        nan_ok: bool = False,
    ) -> object: ...


approx: _ApproxCallable = cast(_ApproxCallable, _approx)


@given(
    tat=st.one_of(
        st.none(),
        st.floats(min_value=0.0, max_value=1000.0, allow_nan=False),
    ),
    now=st.floats(min_value=0.0, max_value=1000.0, allow_nan=False),
    limit=st.integers(min_value=1, max_value=100),
    period=st.floats(min_value=0.001, max_value=1000.0, allow_nan=False),
    burst=st.integers(min_value=1, max_value=50),
)
def test_gcra_step_basic_invariants(
    tat: float | None,
    now: float,
    limit: int,
    period: float,
    burst: int,
) -> None:
    """
    Property test for base GCRA step invariants.

    Checks:
      * delay is non-negative;
      * new TAT is not in the past relative to execution moment;
      * TAT does not exceed execution moment by more than
        interval + tau.
    """
    params = FreqLimitParams(limit=limit, period=period, burst=burst)
    new_tat, delay = gcra_step(now, tat, params)

    assert delay >= 0.0

    effective_now = now + delay

    # TAT cannot precede the execution moment
    assert new_tat >= effective_now

    # And it cannot lead too far (strict GCRA bound)
    assert new_tat - effective_now <= params.interval + params.tau + 1e-9


def test_gcra_step_early_arrival_adds_delay() -> None:
    params = FreqLimitParams(limit=2, period=1.0, burst=1)  # interval = 0.5, tau = 0

    new_tat, delay = gcra_step(now=1.0, tat=1.5, params=params)

    assert delay == approx(0.5, rel=1e-12)
    assert new_tat == approx(2.0, rel=1e-12)


def test_gcra_step_late_arrival_has_zero_delay() -> None:
    params = FreqLimitParams(limit=2, period=1.0, burst=1)

    new_tat, delay = gcra_step(now=2.0, tat=1.5, params=params)

    assert delay == 0.0
    assert new_tat == approx(2.5, rel=1e-12)
