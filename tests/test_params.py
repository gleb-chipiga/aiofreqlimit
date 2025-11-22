from __future__ import annotations

import math
from typing import TypedDict

import pytest
from hypothesis import given, strategies as st

import aiofreqlimit


def test_params_interval_and_tau() -> None:
    params = aiofreqlimit.FreqLimitParams(limit=20, period=60.0, burst=3)
    # interval = 60 / 20 = 3
    assert math.isclose(params.interval, 3.0, rel_tol=1e-12)
    # tau = (burst - 1) * interval = 2 * 3 = 6
    assert math.isclose(params.tau, 6.0, rel_tol=1e-12)


@given(
    limit=st.integers(min_value=1, max_value=100),
    period=st.floats(min_value=0.001, max_value=1000.0, allow_nan=False),
    burst=st.integers(min_value=1, max_value=50),
)
def test_params_valid(limit: int, period: float, burst: int) -> None:
    params = aiofreqlimit.FreqLimitParams(limit=limit, period=period, burst=burst)
    assert params.limit == limit
    assert params.period == period
    assert params.burst == burst
    assert params.interval > 0
    assert params.tau >= 0


class InvalidParams(TypedDict):
    limit: int
    period: float
    burst: int


@pytest.mark.parametrize(
    "kwargs",
    [
        {"limit": 0, "period": 1.0, "burst": 1},
        {"limit": -1, "period": 1.0, "burst": 1},
        {"limit": 1, "period": 0.0, "burst": 1},
        {"limit": 1, "period": -1.0, "burst": 1},
        {"limit": 1, "period": 1.0, "burst": 0},
        {"limit": 1, "period": 1.0, "burst": -1},
    ],
)
def test_params_validation_invalid(kwargs: InvalidParams) -> None:
    with pytest.raises(ValueError):
        _ = aiofreqlimit.FreqLimitParams(
            limit=kwargs["limit"],
            period=kwargs["period"],
            burst=kwargs["burst"],
        )
