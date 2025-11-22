from __future__ import annotations

from .params import FreqLimitParams

__all__ = ("gcra_step",)


def gcra_step(
    now: float,
    tat: float | None,
    params: FreqLimitParams,
) -> tuple[float, float]:
    """
    Single GCRA step (Generic Cell Rate Algorithm) in virtual
    scheduling form.

    Input:
      * now    — current time (same units as tat, usually loop.time())
      * tat    — TAT (Theoretical Arrival Time) for key, or None if new
      * params — limit contract

    Output:
      * new_tat — updated TAT
      * delay   — how long to wait from now to be conforming
    """
    if tat is None:
        tat = now

    interval = params.interval
    tau = params.tau

    # Earliest moment when the packet would be conforming
    allowed_time = tat - tau

    delay = 0.0
    effective_now = now

    if effective_now < allowed_time:
        delay = allowed_time - effective_now
        effective_now = allowed_time

    # GCRA virtual scheduling:
    # - if arrived late      → tat = effective_now + interval
    # - if slightly early    → tat = tat + interval
    tat = effective_now + interval if effective_now >= tat else tat + interval

    return tat, delay
