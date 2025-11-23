from dataclasses import dataclass

__all__ = ("FreqLimitParams",)


@dataclass(frozen=True, slots=True)
class FreqLimitParams:
    """
    GCRA limit parameters:

      * limit  — number of events allowed per period
      * period — window length in seconds
      * burst  — how many events can be squeezed almost at once

    Derived:

      * interval (T) = period / limit
      * tau          = (burst - 1) * interval
    """

    limit: int
    period: float
    burst: int = 1

    def __post_init__(self) -> None:
        if self.limit <= 0:
            raise ValueError("limit must be greater than 0")
        if self.period <= 0:
            raise ValueError("period must be greater than 0")
        if self.burst <= 0:
            raise ValueError("burst must be greater than 0")

    @property
    def interval(self) -> float:
        return self.period / self.limit

    @property
    def tau(self) -> float:
        return self.interval * (self.burst - 1)
