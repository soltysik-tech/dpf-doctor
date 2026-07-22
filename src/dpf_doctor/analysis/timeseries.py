"""Sorted (t, v) series with bisect-backed step lookup."""
import bisect
from typing import Optional


class TS:
    """Fast time-series with bisect lookups."""
    __slots__ = ("ts", "vs")

    def __init__(self, arr: list[tuple[float, float]]) -> None:
        self.ts = [x[0] for x in arr]
        self.vs = [x[1] for x in arr]

    def at(self, t: float) -> Optional[float]:
        if not self.ts:
            return None
        i = bisect.bisect_right(self.ts, t) - 1
        if i < 0:
            return None
        return self.vs[i]
